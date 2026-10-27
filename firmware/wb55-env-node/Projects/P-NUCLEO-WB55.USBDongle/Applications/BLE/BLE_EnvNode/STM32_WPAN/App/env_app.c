/**
  ******************************************************************************
  * @file    env_app.c
  * @brief   Environmental Sensor Service Application - reads the SCD30
  *          (CO2/temperature/humidity) on a repeating timer and pushes the
  *          values into the custom Environmental Sensor Service (envs.c).
  ******************************************************************************
  */

#include "app_common.h"
#include "dbg_trace.h"

#include "ble.h"
#include "envs.h"
#include "stm32_seq.h"
#include "scd30.h"
#include <string.h>

typedef struct
{
  uint8_t TimerMeasurement_Id;
} ENVAPP_Context_t;

#define ENVAPP_MEASUREMENT_INTERVAL   (2000000 / CFG_TS_TICK_VAL) /**< 2s, matches SCD30's measurement interval */

static ENVAPP_Context_t ENVAPP_Context;

static void EnvMeas(void);
static void ENVAPP_Measurement(void);

void ENVS_Notification(ENVS_App_Notification_evt_t *pNotification)
{
  /* Measurement runs continuously from boot (see ENVAPP_Init) so that plain
   * characteristic reads work without a client subscribing first - nothing
   * to do here, subscription state only controls whether the stack sends
   * notifications, which it already handles on its own. */
  (void)pNotification;
}

void ENVAPP_Init(void)
{
  UTIL_SEQ_RegTask(1 << CFG_TASK_MEAS_REQ_ID, UTIL_SEQ_RFU, ENVAPP_Measurement);

  HW_TS_Create(CFG_TIM_PROC_ID_ISR, &(ENVAPP_Context.TimerMeasurement_Id), hw_ts_Repeated, EnvMeas);

  SCD30_Init();

  /* Measure continuously from boot, independent of BLE notification
   * subscription, so a plain characteristic Read always returns a fresh
   * value instead of the power-on default. */
  HW_TS_Start(ENVAPP_Context.TimerMeasurement_Id, ENVAPP_MEASUREMENT_INTERVAL);
}

static void ENVAPP_Measurement(void)
{
  float co2_ppm;
  float temperature_c;
  float humidity_rh;
  uint16_t co2_raw;
  int16_t temperature_raw;
  uint16_t humidity_raw;

  if (!SCD30_DataReady())
  {
    APP_DBG_MSG("ENVAPP: SCD30 not ready\n");
    return;
  }

  if (!SCD30_ReadMeasurement(&co2_ppm, &temperature_c, &humidity_rh))
  {
    APP_DBG_MSG("ENVAPP: SCD30 read failed (I2C or CRC error)\n");
    return;
  }

  /* Temperature/humidity are sent as int16/uint16 x100 - plain integers
   * that any BLE inspector app can decode without a float parser. */
  co2_raw = (uint16_t)co2_ppm;
  temperature_raw = (int16_t)(temperature_c * 100.0f);
  humidity_raw = (uint16_t)(humidity_rh * 100.0f);

  APP_DBG_MSG("ENVAPP: CO2=%d ppm  Temp=%d.%02d C  RH=%d.%02d %%  (raw co2=0x%04X temp=0x%04X rh=0x%04X)\n",
              (int)co2_raw,
              temperature_raw / 100, (temperature_raw < 0 ? -temperature_raw : temperature_raw) % 100,
              humidity_raw / 100, humidity_raw % 100,
              co2_raw, (uint16_t)temperature_raw, humidity_raw);

  ENVS_UpdateChar(ENVS_UUID_CO2, (uint8_t *)&co2_raw);
  ENVS_UpdateChar(ENVS_UUID_TEMPERATURE, (uint8_t *)&temperature_raw);
  ENVS_UpdateChar(ENVS_UUID_HUMIDITY, (uint8_t *)&humidity_raw);
}

static void EnvMeas(void)
{
  /**
   * The code shall be executed in the background as aci command may be sent
   * The background is the only place where the application can make sure a new aci command
   * is not sent if there is a pending one
   */
  UTIL_SEQ_SetTask(1 << CFG_TASK_MEAS_REQ_ID, CFG_SCH_PRIO_0);
}
