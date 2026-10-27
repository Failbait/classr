/**
  ******************************************************************************
  * @file    envs.h
  * @brief   Custom "Environmental Sensor Service" - CO2/temperature/humidity
  *          over BLE, using a private 128-bit service UUID (not the standard
  *          Heart Rate Service).
  ******************************************************************************
  */

#ifndef ENVS_H
#define ENVS_H

#ifdef __cplusplus
extern "C" {
#endif

#include <stdint.h>

typedef enum
{
  ENVS_UUID_CO2 = 1,
  ENVS_UUID_TEMPERATURE,
  ENVS_UUID_HUMIDITY,
} ENVS_CharUUID_t;

typedef enum
{
  ENVS_NOTIFICATION_ENABLED,
  ENVS_NOTIFICATION_DISABLED,
} ENVS_NotCode_t;

typedef struct
{
  ENVS_NotCode_t ENVS_Evt_Opcode;
} ENVS_App_Notification_evt_t;

void ENVS_Init(void);
/* 16-byte service UUID, LSB first, for the advertising service list */
const uint8_t *ENVS_GetServiceUuid(void);
tBleStatus ENVS_UpdateChar(ENVS_CharUUID_t uuid, uint8_t *p_payload);
void ENVS_Notification(ENVS_App_Notification_evt_t *pNotification);

#ifdef __cplusplus
}
#endif

#endif /* ENVS_H */
