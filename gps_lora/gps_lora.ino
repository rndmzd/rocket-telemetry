#include <Arduino.h>
#include <SPI.h>
#include <Wire.h>
#include <RH_RF95.h>     // LoRa (RFM9x)
#include <TinyGPSPlus.h> // GPS parsing
#include <Adafruit_Sensor.h>
#include <Adafruit_LSM303_Accel.h>
#include <Adafruit_LSM303DLH_Mag.h>
#include <Adafruit_L3GD20_U.h>
#include <Adafruit_BMP085_U.h>
#include <SD.h>
#include "TimeLib.h"

#define DEBUG_MODE

#ifdef DEBUG_MODE
bool debug = true;
#else
bool debug = false;
#endif

#define RF95_FREQ 433.0
#define RF95_TX_POWER 2

// ----------------- LoRa Module Pins -----------------
#define RFM95_CS 10 // LoRa Chip Select for M0
#define RFM95_RST 9 // LoRa Reset for M0
#define RFM95_INT 3 // Connect to G0 on LoRa module
RH_RF95 rf95(RFM95_CS, RFM95_INT);

// ----------------- GPS Setup -----------------
// Using hardware Serial1 (pins 0 & 1) on M0 for GPS
#define GPSSerial Serial1
TinyGPSPlus gps;

// LoRa transmission interval
uint32_t lastLoRaSend = 0;
const uint32_t sendInterval = 10000; // 1 second

// ----------------- 10-DOF Sensor Objects -----------------
Adafruit_LSM303_Accel_Unified accel = Adafruit_LSM303_Accel_Unified(30301);
Adafruit_LSM303DLH_Mag_Unified mag = Adafruit_LSM303DLH_Mag_Unified(30302);
Adafruit_L3GD20_Unified gyro = Adafruit_L3GD20_Unified(20);
Adafruit_BMP085_Unified bmp = Adafruit_BMP085_Unified(18001);

// Add these definitions
#define SD_CS 4           // SD Card CS pin for M0 Adalogger
#define BUFFER_SIZE 512   // Optimal buffer size for SD writing
char buffer[BUFFER_SIZE]; // Buffer for SD writing
File dataFile;            // File object

// Add at top with other globals
enum TransmitState
{
  IDLE,
  SENDING_GPS,
  SENDING_IMU
};
TransmitState txState = IDLE;
char gps_packet[64];
char imu_packet[128];

void setup()
{
  Serial.begin(115200);
  // Remove while(!Serial) to allow standalone operation
  delay(5000); // Give some time for serial monitor connection if needed

  // -------- Initialize GPS --------
  GPSSerial.begin(9600); // Ultimate GPS runs at 9600 baud

  // -------- Reset and Initialize LoRa --------
  pinMode(RFM95_RST, OUTPUT);
  digitalWrite(RFM95_RST, LOW);
  delay(10);
  digitalWrite(RFM95_RST, HIGH);
  delay(10);

  if (!rf95.init())
  {
    Serial.println("LoRa init failed!");
    while (1)
      ;
  }
  rf95.setFrequency(RF95_FREQ);
  rf95.setTxPower(RF95_TX_POWER, false);

  // Initialize 10-DOF sensors
  if (!accel.begin())
  {
    Serial.println("LSM303 Accelerometer not detected!");
    while (1)
      ;
  }
  if (!mag.begin())
  {
    Serial.println("LSM303 Magnetometer not detected!");
    while (1)
      ;
  }
  if (!gyro.begin())
  {
    Serial.println("L3GD20 Gyroscope not detected!");
    while (1)
      ;
  }
  if (!bmp.begin())
  {
    Serial.println("BMP085 not detected!");
    while (1)
      ;
  }

  // Initialize SD card
  if (!SD.begin(SD_CS))
  {
    Serial.println("SD card initialization failed!");
    while (1)
      ;
  }
  Serial.println("SD card initialized.");

  // Create new file with timestamp
  char filename[32];
  sprintf(filename, "FLIGHT_%lu.csv", now()); // Uses TimeLib for timestamp
  dataFile = SD.open(filename, FILE_WRITE);
  if (!dataFile)
  {
    Serial.println("Failed to create file!");
    while (1)
      ;
  }

  // Write CSV header
  dataFile.println("timestamp,lat,lng,alt,ax,ay,az,mx,my,mz,gx,gy,gz,pressure,temp");
}

void get10DOFData(char *buffer, size_t bufferSize)
{
  sensors_event_t accel_event, mag_event, gyro_event, bmp_event;

  accel.getEvent(&accel_event);
  mag.getEvent(&mag_event);
  gyro.getEvent(&gyro_event);
  bmp.getEvent(&bmp_event);

  float temperature;
  bmp.getTemperature(&temperature);

  snprintf(buffer, bufferSize,
           "ACC=%.2f,%.2f,%.2f"
           ",MAG=%.2f,%.2f,%.2f"
           ",GYRO=%.2f,%.2f,%.2f"
           ",PRES=%.2f,TEMP=%.2f",
           accel_event.acceleration.x, accel_event.acceleration.y, accel_event.acceleration.z,
           mag_event.magnetic.x, mag_event.magnetic.y, mag_event.magnetic.z,
           gyro_event.gyro.x, gyro_event.gyro.y, gyro_event.gyro.z,
           bmp_event.pressure, temperature);
}

// Add this function for efficient SD writing
void logData(const sensors_event_t &accel, const sensors_event_t &mag,
             const sensors_event_t &gyro, const sensors_event_t &bmp,
             float temp)
{
  // Format data into buffer
  int len = snprintf(buffer, BUFFER_SIZE,
                     "%lu,%.6f,%.6f,%.2f,%.2f,%.2f,%.2f,%.2f,%.2f,%.2f,%.2f,%.2f,%.2f,%.2f,%.2f\n",
                     millis(),
                     gps.location.isValid() ? gps.location.lat() : 0.0,
                     gps.location.isValid() ? gps.location.lng() : 0.0,
                     gps.altitude.isValid() ? gps.altitude.meters() : 0.0,
                     accel.acceleration.x, accel.acceleration.y, accel.acceleration.z,
                     mag.magnetic.x, mag.magnetic.y, mag.magnetic.z,
                     gyro.gyro.x, gyro.gyro.y, gyro.gyro.z,
                     bmp.pressure, temp);

  // Write buffer to SD
  if (len > 0 && len < BUFFER_SIZE)
  {
    dataFile.write(buffer, len);
    // Flush every few writes to prevent data loss
    static uint32_t writeCount = 0;
    if (++writeCount % 10 == 0)
    {
      dataFile.flush();
    }
  }
}

void loop()
{
  uint32_t now = millis();

  // Always read GPS and sensor data
  while (GPSSerial.available())
  {
    gps.encode(GPSSerial.read());
  }

  // Get sensor readings and log to SD (runs at full speed)
  sensors_event_t accel_event, mag_event, gyro_event, bmp_event;
  float temperature;

  accel.getEvent(&accel_event);
  mag.getEvent(&mag_event);
  gyro.getEvent(&gyro_event);
  bmp.getEvent(&bmp_event);
  bmp.getTemperature(&temperature);

  // Log data to SD (runs at full speed)
  logData(accel_event, mag_event, gyro_event, bmp_event, temperature);

  // Non-blocking LoRa state machine
  if (now - lastLoRaSend >= sendInterval)
  {
    if (txState == IDLE)
    {
      // Prepare new transmission
      if (gps.location.isValid())
      {
        // Format GPS packet
        float lat = gps.location.lat();
        float lng = gps.location.lng();
        float alt = gps.altitude.meters();
        snprintf(gps_packet, sizeof(gps_packet),
                 "LAT=%.6f,LNG=%.6f,ALT=%.2f", lat, lng, alt);

        // Start GPS transmission
        rf95.send((uint8_t *)gps_packet, strlen(gps_packet));
        txState = SENDING_GPS;
      }
      else
      {
        rf95.send((uint8_t *)"NO_GPS_FIX", 10);
        txState = SENDING_GPS;
      }
      lastLoRaSend = now;
    }
    else if (txState == SENDING_GPS && rf95.waitPacketSent(0))
    { // Non-blocking check
      // GPS packet sent, start IMU packet
      get10DOFData(imu_packet, sizeof(imu_packet));
      rf95.send((uint8_t *)imu_packet, strlen(imu_packet));
      txState = SENDING_IMU;
    }
    else if (txState == SENDING_IMU && rf95.waitPacketSent(0))
    { // Non-blocking check
      // IMU packet sent, transmission complete
      txState = IDLE;
    }
  }

  if (debug)
  {
    // Print sensor readings (could also be made less frequent if desired)
    printSensorReadings(accel_event, mag_event, gyro_event, bmp_event, temperature);
  }
}

// Move the sensor printing to a separate function to keep loop() cleaner
void printSensorReadings(const sensors_event_t &accel, const sensors_event_t &mag,
                         const sensors_event_t &gyro, const sensors_event_t &bmp,
                         float temperature)
{
  // Print sensor data every loop iteration
  Serial.println("------ Sensor Readings ------");
  Serial.print("Accel: X=");
  Serial.print(accel.acceleration.x);
  Serial.print(" Y=");
  Serial.print(accel.acceleration.y);
  Serial.print(" Z=");
  Serial.print(accel.acceleration.z);
  Serial.println(" m/s^2");

  Serial.print("Mag: X=");
  Serial.print(mag.magnetic.x);
  Serial.print(" Y=");
  Serial.print(mag.magnetic.y);
  Serial.print(" Z=");
  Serial.print(mag.magnetic.z);
  Serial.println(" uT");

  Serial.print("Gyro: X=");
  Serial.print(gyro.gyro.x);
  Serial.print(" Y=");
  Serial.print(gyro.gyro.y);
  Serial.print(" Z=");
  Serial.print(gyro.gyro.z);
  Serial.println(" rad/s");

  Serial.print("Pressure: ");
  Serial.print(bmp.pressure);
  Serial.print(" hPa, Temp: ");
  Serial.print(temperature);
  Serial.println(" °C");
  Serial.println("--------------------------");
  Serial.println();
}
