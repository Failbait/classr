/**
  ******************************************************************************
  * @file    scd30.c
  * @brief   Minimal blocking I2C driver for the Sensirion SCD30 CO2/T/RH sensor.
  *          Reference: Sensirion SCD30 Interface Description.
  ******************************************************************************
  */

#include "scd30.h"
#include "main.h"
#include <string.h>

#define SCD30_I2C_ADDR            (0x61 << 1)
#define SCD30_I2C_TIMEOUT_MS      100

#define SCD30_CMD_TRIGGER_MEAS    0x0010
#define SCD30_CMD_DATA_READY      0x0202
#define SCD30_CMD_READ_MEAS       0x0300

static uint8_t SCD30_CRC8(const uint8_t *data, uint8_t len)
{
  uint8_t crc = 0xFF;

  for (uint8_t i = 0; i < len; i++)
  {
    crc ^= data[i];
    for (uint8_t bit = 0; bit < 8; bit++)
    {
      crc = (crc & 0x80) ? (uint8_t)((crc << 1) ^ 0x31) : (uint8_t)(crc << 1);
    }
  }

  return crc;
}

static bool SCD30_SendCommand(uint16_t command, const uint16_t *argument)
{
  uint8_t buf[5];
  uint8_t len;

  buf[0] = (uint8_t)(command >> 8);
  buf[1] = (uint8_t)(command & 0xFF);
  len = 2;

  if (argument != NULL)
  {
    buf[2] = (uint8_t)(*argument >> 8);
    buf[3] = (uint8_t)(*argument & 0xFF);
    buf[4] = SCD30_CRC8(&buf[2], 2);
    len = 5;
  }

  return HAL_I2C_Master_Transmit(&hi2c1, SCD30_I2C_ADDR, buf, len, SCD30_I2C_TIMEOUT_MS) == HAL_OK;
}

static bool SCD30_ReadWords(uint8_t *rx_buf, uint8_t rx_len)
{
  return HAL_I2C_Master_Receive(&hi2c1, SCD30_I2C_ADDR, rx_buf, rx_len, SCD30_I2C_TIMEOUT_MS) == HAL_OK;
}

bool SCD30_Init(void)
{
  uint16_t no_pressure_comp = 0x0000;

  return SCD30_SendCommand(SCD30_CMD_TRIGGER_MEAS, &no_pressure_comp);
}

bool SCD30_DataReady(void)
{
  uint8_t rx[3];

  if (!SCD30_SendCommand(SCD30_CMD_DATA_READY, NULL))
  {
    return false;
  }

  HAL_Delay(3); /* SCD30 needs >3 ms to prepare the response, see datasheet */

  if (!SCD30_ReadWords(rx, sizeof(rx)))
  {
    return false;
  }

  if (SCD30_CRC8(rx, 2) != rx[2])
  {
    return false;
  }

  return ((rx[0] << 8) | rx[1]) != 0;
}

bool SCD30_ReadMeasurement(float *co2_ppm, float *temperature_c, float *humidity_rh)
{
  uint8_t rx[18];
  uint32_t words[6];

  if (!SCD30_SendCommand(SCD30_CMD_READ_MEAS, NULL))
  {
    return false;
  }

  HAL_Delay(3); /* SCD30 needs >3 ms to prepare the response, see datasheet */

  if (!SCD30_ReadWords(rx, sizeof(rx)))
  {
    return false;
  }

  for (uint8_t i = 0; i < 6; i++)
  {
    const uint8_t *word = &rx[i * 3];

    if (SCD30_CRC8(word, 2) != word[2])
    {
      return false;
    }

    words[i] = ((uint32_t)word[0] << 8) | word[1];
  }

  uint32_t co2_bits = (words[0] << 16) | words[1];
  uint32_t temp_bits = (words[2] << 16) | words[3];
  uint32_t rh_bits = (words[4] << 16) | words[5];

  float co2_value;
  float temp_value;
  float rh_value;

  memcpy(&co2_value, &co2_bits, sizeof(co2_value));
  memcpy(&temp_value, &temp_bits, sizeof(temp_value));
  memcpy(&rh_value, &rh_bits, sizeof(rh_value));

  *co2_ppm = co2_value;
  *temperature_c = temp_value;
  *humidity_rh = rh_value;

  return true;
}
