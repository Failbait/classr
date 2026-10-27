/**
  ******************************************************************************
  * @file    scd30.h
  * @brief   Minimal blocking I2C driver for the Sensirion SCD30 CO2/T/RH sensor.
  ******************************************************************************
  */

#ifndef SCD30_H
#define SCD30_H

#ifdef __cplusplus
extern "C" {
#endif

#include <stdint.h>
#include <stdbool.h>

/**
  * @brief  Starts continuous measurement on the SCD30 (default 2 s interval,
  *         no ambient pressure compensation).
  * @retval true on success, false on I2C error
  */
bool SCD30_Init(void);

/**
  * @brief  Checks whether a new measurement is available to read.
  * @retval true if a measurement is ready
  */
bool SCD30_DataReady(void);

/**
  * @brief  Reads the latest CO2/temperature/humidity measurement.
  * @param  co2_ppm       Output: CO2 concentration in ppm
  * @param  temperature_c Output: temperature in degrees Celsius
  * @param  humidity_rh   Output: relative humidity in percent
  * @retval true on success (including CRC checks), false on I2C or CRC error
  */
bool SCD30_ReadMeasurement(float *co2_ppm, float *temperature_c, float *humidity_rh);

#ifdef __cplusplus
}
#endif

#endif /* SCD30_H */
