/**
  ******************************************************************************
  * @file    envs.c
  * @brief   Custom "Environmental Sensor Service" - CO2/temperature/humidity
  *          over BLE, using a private 128-bit service UUID (not the standard
  *          Heart Rate Service). Modeled on Middlewares/ST/STM32_WPAN/ble/svc
  *          /Src/hrs.c, simplified to plain notify/read characteristics.
  ******************************************************************************
  */

#include "app_common.h"
#include "dbg_trace.h"
#include "common_blesvc.h"
#include "envs.h"

typedef struct
{
  uint16_t ServiceHdle;
  uint16_t Co2CharHdle;
  uint16_t TemperatureCharHdle;
  uint16_t HumidityCharHdle;
  uint8_t  NotificationEnabledMask; /* bit0=CO2, bit1=temperature, bit2=humidity */
} ENVS_Context_t;

/**
 * Environmental Sensor Service and characteristic UUIDs, private 128-bit,
 * base 0000xxxx-4A34-4B2A-9D0C-53574F495430 ("SWIOT0" spelled out in the
 * last 6 bytes). Byte order is reversed (LSB first) as required by
 * aci_gatt_add_service()/aci_gatt_add_char().
 */
static const uint8_t ENVS_SERVICE_UUID[16] =
  {0x30, 0x54, 0x49, 0x4F, 0x57, 0x53, 0x0C, 0x9D, 0x2A, 0x4B, 0x34, 0x4A, 0x00, 0xA0, 0x00, 0x00};
static const uint8_t ENVS_CO2_CHAR_UUID[16] =
  {0x30, 0x54, 0x49, 0x4F, 0x57, 0x53, 0x0C, 0x9D, 0x2A, 0x4B, 0x34, 0x4A, 0x01, 0xA0, 0x00, 0x00};
static const uint8_t ENVS_TEMPERATURE_CHAR_UUID[16] =
  {0x30, 0x54, 0x49, 0x4F, 0x57, 0x53, 0x0C, 0x9D, 0x2A, 0x4B, 0x34, 0x4A, 0x02, 0xA0, 0x00, 0x00};
static const uint8_t ENVS_HUMIDITY_CHAR_UUID[16] =
  {0x30, 0x54, 0x49, 0x4F, 0x57, 0x53, 0x0C, 0x9D, 0x2A, 0x4B, 0x34, 0x4A, 0x03, 0xA0, 0x00, 0x00};

const uint8_t *ENVS_GetServiceUuid(void)
{
  return ENVS_SERVICE_UUID;
}

PLACE_IN_SECTION("BLE_DRIVER_CONTEXT") static ENVS_Context_t ENVS_Context;

static SVCCTL_EvtAckStatus_t ENVS_Event_Handler(void *Event)
{
  SVCCTL_EvtAckStatus_t return_value = SVCCTL_EvtNotAck;
  hci_event_pckt *event_pckt;
  evt_blecore_aci *blecore_evt;
  aci_gatt_attribute_modified_event_rp0 *attribute_modified;
  ENVS_App_Notification_evt_t Notification;
  uint8_t char_bit = 0;
  uint8_t previous_mask;

  event_pckt = (hci_event_pckt *)(((hci_uart_pckt *)Event)->data);

  if (event_pckt->evt != HCI_VENDOR_SPECIFIC_DEBUG_EVT_CODE)
  {
    return return_value;
  }

  blecore_evt = (evt_blecore_aci *)event_pckt->data;

  if (blecore_evt->ecode != ACI_GATT_ATTRIBUTE_MODIFIED_VSEVT_CODE)
  {
    return return_value;
  }

  attribute_modified = (aci_gatt_attribute_modified_event_rp0 *)blecore_evt->data;

  if (attribute_modified->Attr_Handle == (ENVS_Context.Co2CharHdle + 2))
  {
    char_bit = 1u << 0;
  }
  else if (attribute_modified->Attr_Handle == (ENVS_Context.TemperatureCharHdle + 2))
  {
    char_bit = 1u << 1;
  }
  else if (attribute_modified->Attr_Handle == (ENVS_Context.HumidityCharHdle + 2))
  {
    char_bit = 1u << 2;
  }

  if (char_bit == 0)
  {
    return return_value;
  }

  return_value = SVCCTL_EvtAckFlowEnable;
  previous_mask = ENVS_Context.NotificationEnabledMask;

  if (attribute_modified->Attr_Data[0] & COMSVC_Notification)
  {
    ENVS_Context.NotificationEnabledMask |= char_bit;
  }
  else
  {
    ENVS_Context.NotificationEnabledMask &= (uint8_t)~char_bit;
  }

  if (previous_mask == 0 && ENVS_Context.NotificationEnabledMask != 0)
  {
    Notification.ENVS_Evt_Opcode = ENVS_NOTIFICATION_ENABLED;
    ENVS_Notification(&Notification);
  }
  else if (previous_mask != 0 && ENVS_Context.NotificationEnabledMask == 0)
  {
    Notification.ENVS_Evt_Opcode = ENVS_NOTIFICATION_DISABLED;
    ENVS_Notification(&Notification);
  }

  return return_value;
}

void ENVS_Init(void)
{
  tBleStatus status;

  SVCCTL_RegisterSvcHandler(ENVS_Event_Handler);

  status = aci_gatt_add_service(UUID_TYPE_128,
                                 (Service_UUID_t *)ENVS_SERVICE_UUID,
                                 PRIMARY_SERVICE,
                                 10, /* 1 svc + 3 * (2 for char decl+value + 1 CCCD) */
                                 &(ENVS_Context.ServiceHdle));
  APP_DBG_MSG("ENVS: aci_gatt_add_service status=0x%02X hdle=0x%04X\n", status, ENVS_Context.ServiceHdle);

  status = aci_gatt_add_char(ENVS_Context.ServiceHdle,
                              UUID_TYPE_128,
                              (Char_UUID_t *)ENVS_CO2_CHAR_UUID,
                              2, /* uint16, ppm */
                              CHAR_PROP_READ | CHAR_PROP_NOTIFY,
                              ATTR_PERMISSION_NONE,
                              GATT_DONT_NOTIFY_EVENTS,
                              10,
                              0,
                              &(ENVS_Context.Co2CharHdle));
  APP_DBG_MSG("ENVS: add CO2 char status=0x%02X hdle=0x%04X\n", status, ENVS_Context.Co2CharHdle);

  status = aci_gatt_add_char(ENVS_Context.ServiceHdle,
                              UUID_TYPE_128,
                              (Char_UUID_t *)ENVS_TEMPERATURE_CHAR_UUID,
                              2, /* int16, degC x 100 */
                              CHAR_PROP_READ | CHAR_PROP_NOTIFY,
                              ATTR_PERMISSION_NONE,
                              GATT_DONT_NOTIFY_EVENTS,
                              10,
                              0,
                              &(ENVS_Context.TemperatureCharHdle));
  APP_DBG_MSG("ENVS: add temperature char status=0x%02X hdle=0x%04X\n", status, ENVS_Context.TemperatureCharHdle);

  status = aci_gatt_add_char(ENVS_Context.ServiceHdle,
                              UUID_TYPE_128,
                              (Char_UUID_t *)ENVS_HUMIDITY_CHAR_UUID,
                              2, /* uint16, %RH x 100 */
                              CHAR_PROP_READ | CHAR_PROP_NOTIFY,
                              ATTR_PERMISSION_NONE,
                              GATT_DONT_NOTIFY_EVENTS,
                              10,
                              0,
                              &(ENVS_Context.HumidityCharHdle));
  APP_DBG_MSG("ENVS: add humidity char status=0x%02X hdle=0x%04X\n", status, ENVS_Context.HumidityCharHdle);
}

tBleStatus ENVS_UpdateChar(ENVS_CharUUID_t uuid, uint8_t *p_payload)
{
  switch (uuid)
  {
    case ENVS_UUID_CO2:
      return aci_gatt_update_char_value(ENVS_Context.ServiceHdle, ENVS_Context.Co2CharHdle, 0, 2, p_payload);

    case ENVS_UUID_TEMPERATURE:
      return aci_gatt_update_char_value(ENVS_Context.ServiceHdle, ENVS_Context.TemperatureCharHdle, 0, 2, p_payload);

    case ENVS_UUID_HUMIDITY:
      return aci_gatt_update_char_value(ENVS_Context.ServiceHdle, ENVS_Context.HumidityCharHdle, 0, 2, p_payload);

    default:
      return BLE_STATUS_INVALID_PARAMS;
  }
}

/**
 * Strong override of the weak SVCCTL_InitCustomSvc() extension point in
 * svc_ctl.c - called automatically at the end of SVCCTL_SvcInit().
 */
void SVCCTL_InitCustomSvc(void)
{
  ENVS_Init();
}
