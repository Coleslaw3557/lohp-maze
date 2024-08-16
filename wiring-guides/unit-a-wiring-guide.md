# LoHP Maze Wiring Guide
# UNIT - A

## Raspberry Pi Full 40-pin Pinout Connections

| Pin | GPIO | Function | Connection |
|-----|------|----------|------------|
| 1   | 3V3  | Power    | LS1 VCCA, LS2 VCCA, LS1 OE, LS2 OE, ADS1115 VDD, Resistor Ladder VCC |
| 2   | 5V   | Power    | LS1 VCCB, LS2 VCCB, All Laser Module VCC |
| 3   | GPIO2| I2C SDA  | ADS1115 SDA |
| 4   | 5V   | Power    | Not used (available if needed) |
| 5   | GPIO3| I2C SCL  | ADS1115 SCL |
| 6   | GND  | Ground   | LS1 GND, LS2 GND, ADS1115 GND, All Laser Module GND, Resistor Ladder GND |
| 7   | GPIO4| GPIO     | Entrance LT (via LS1) |
| 8   | GPIO14| UART TXD| Not used (reserved for console access) |
| 9   | GND  | Ground   | Not used (available if needed) |
| 10  | GPIO15| UART RXD| Not used (reserved for console access) |
| 11  | GPIO17| GPIO    | Entrance LR (via LS1) |
| 12  | GPIO18| GPIO    | Cuddle Cross LT (via LS1) |
| 13  | GPIO27| GPIO    | Cuddle Cross LR (via LS1) |
| 14  | GND  | Ground   | Not used (available if needed) |
| 15  | GPIO22| GPIO    | Photo Bomb LT (via LS2) |
| 16  | GPIO23| GPIO    | Photo Bomb LR (via LS2) |
| 17  | 3V3  | Power    | Not used (available if needed) |
| 18  | GPIO24| GPIO    | No Friends Monday LT (via LS2) |
| 19  | GPIO10| SPI MOSI| Not used |
| 20  | GND  | Ground   | Not used (available if needed) |
| 21  | GPIO9 | SPI MISO| Not used |
| 22  | GPIO25| GPIO    | No Friends Monday LR (via LS2) |
| 23  | GPIO11| SPI SCLK| Not used |
| 24  | GPIO8 | SPI CE0 | Not used |
| 25  | GND  | Ground   | Not used (available if needed) |
| 26  | GPIO7 | SPI CE1 | Not used |
| 27  | ID_SD | I2C ID EEPROM | Not used (reserved for HAT ID EEPROM) |
| 28  | ID_SC | I2C ID EEPROM | Not used (reserved for HAT ID EEPROM) |
| 29  | GPIO5 | GPIO    | Exit LT (via LS2) |
| 30  | GND  | Ground   | Not used (available if needed) |
| 31  | GPIO6 | GPIO    | Exit LR (via LS2) |
| 32  | GPIO12| GPIO    | Not used |
| 33  | GPIO13| GPIO    | Not used |
| 34  | GND  | Ground   | Not used (available if needed) |
| 35  | GPIO19| GPIO    | Not used |
| 36  | GPIO16| GPIO    | Not used |
| 37  | GPIO26| GPIO    | Not used |
| 38  | GPIO20| GPIO    | Not used |
| 39  | GND  | Ground   | Not used (available if needed) |
| 40  | GPIO21| GPIO    | Not used |

## Raspberry Pi GPIO Connections

| Room | Component | Physical Pin | GPIO | Connection |
|------|-----------|--------------|------|------------|
| All | I2C SDA | 3 | 2 | ADS1115 SDA |
| All | I2C SCL | 5 | 3 | ADS1115 SCL |
| Entrance | LT | 7 | 4 | Via LS1 |
| Entrance | LR | 11 | 17 | Via LS1 |
| Cuddle Cross | LT | 12 | 18 | Via LS1 |
| Cuddle Cross | LR | 13 | 27 | Via LS1 |
| Photo Bomb | LT | 15 | 22 | Via LS2 |
| Photo Bomb | LR | 16 | 23 | Via LS2 |
| No Friends Monday | LT | 18 | 24 | Via LS2 |
| No Friends Monday | LR | 22 | 25 | Via LS2 |
| Exit | LT | 29 | 5 | Via LS2 |
| Exit | LR | 31 | 6 | Via LS2 |

## Power Connections

| Voltage | Physical Pin | Connections |
|---------|--------------|-------------|
| 3.3V | 1 | LS1 VCCA, LS2 VCCA, LS1 OE, LS2 OE, ADS1115 VDD, Resistor Ladder VCC |
| 5V | 2 | LS1 VCCB, LS2 VCCB, All Laser Module VCC |
| GND | 6 | LS1 GND, LS2 GND, ADS1115 GND, All Laser Module GND, Resistor Ladder GND |

## Additional GND Connections (if needed)
| Voltage | Physical Pin | Purpose |
|---------|--------------|---------|
| GND | 9 | Spare GND |
| GND | 14 | Spare GND |
| GND | 20 | Spare GND |
| GND | 25 | Spare GND |
| GND | 30 | Spare GND |
| GND | 34 | Spare GND |
| GND | 39 | Spare GND |

## Level Shifters (TXS0108E)

### LS1 (Entrance and Cuddle Cross Rooms)

| Pin | Connection |
|-----|------------|
| VCCA | 3.3V (Pi Pin 1) |
| VCCB | 5V (Pi Pin 2) |
| GND | GND (Pi Pin 6) |
| OE | 3.3V (Pi Pin 1) |
| A1 | Raspberry Pi GPIO 4 (Pi Pin 7) |
| B1 | Entrance LT Signal |
| A2 | Raspberry Pi GPIO 17 (Pi Pin 11) |
| B2 | Entrance LR Signal |
| A3 | Raspberry Pi GPIO 18 (Pi Pin 12) |
| B3 | Cuddle Cross LT Signal |
| A4 | Raspberry Pi GPIO 27 (Pi Pin 13) |
| B4 | Cuddle Cross LR Signal |
| A5-A8 | Not Connected |
| B5-B8 | Not Connected |

### LS2 (Photo Bomb, No Friends Monday, and Exit Rooms)

| Pin | Connection |
|-----|------------|
| VCCA | 3.3V (Pi Pin 1) |
| VCCB | 5V (Pi Pin 2) |
| GND | GND (Pi Pin 6) |
| OE | 3.3V (Pi Pin 1) |
| A1 | Raspberry Pi GPIO 22 (Pi Pin 15) |
| B1 | Photo Bomb LT Signal |
| A2 | Raspberry Pi GPIO 23 (Pi Pin 16) |
| B2 | Photo Bomb LR Signal |
| A3 | Raspberry Pi GPIO 24 (Pi Pin 18) |
| B3 | No Friends Monday LT Signal |
| A4 | Raspberry Pi GPIO 25 (Pi Pin 22) |
| B4 | No Friends Monday LR Signal |
| A5 | Raspberry Pi GPIO 5 (Pi Pin 29) |
| B5 | Exit LT Signal |
| A6 | Raspberry Pi GPIO 6 (Pi Pin 31) |
| B6 | Exit LR Signal |
| A7-A8 | Not Connected |
| B7-B8 | Not Connected |

## ADS1115 ADC

### ADC (Cuddle Cross Room)

| Pin | Connection |
|-----|------------|
| VDD | 3.3V (Pi Pin 1) |
| GND | GND (Pi Pin 6) |
| SCL | Raspberry Pi GPIO 3 (Pi Pin 5) |
| SDA | Raspberry Pi GPIO 2 (Pi Pin 3) |
| A0 | Resistor Ladder Signal |
| A1 | Not Connected |
| A2 | Not Connected |
| A3 | Not Connected |
| ADDR | GND (Pi Pin 6) (I2C address 0x48) |

## Laser Modules

### Laser Transmitters (LT)

| Room | GPIO | Physical Pin | Connection |
|------|------|--------------|------------|
| Entrance | 4 | 7 | LS1 B1 |
| Cuddle Cross | 18 | 12 | LS1 B3 |
| Photo Bomb | 22 | 15 | LS2 B1 |
| No Friends Monday | 24 | 18 | LS2 B3 |
| Exit | 5 | 29 | LS2 B5 |

### Laser Receivers (LR)

| Room | GPIO | Physical Pin | Connection |
|------|------|--------------|------------|
| Entrance | 17 | 11 | LS1 B2 |
| Cuddle Cross | 27 | 13 | LS1 B4 |
| Photo Bomb | 23 | 16 | LS2 B2 |
| No Friends Monday | 25 | 22 | LS2 B4 |
| Exit | 6 | 31 | LS2 B6 |

## Analog Sensors

### Cuddle Cross Room

| Sensor | Connection |
|--------|------------|
| Resistor Ladder (10k resistors) | ADC A0 |

## Additional Notes

1. All laser modules (LT and LR) have their VCC connected to 5V (Pi Pin 2) and GND connected to the main GND (Pi Pin 6).
2. The resistor ladder in the Cuddle Cross room has its VCC connected to 3.3V (Pi Pin 1) and GND connected to the main GND (Pi Pin 6).
3. Ensure all GND connections are properly made to create a common ground for the entire system.
4. Double-check all connections before powering on the Raspberry Pi to prevent any potential damage to the components.
5. The UART pins (GPIO 14 and 15, or physical pins 8 and 10) are left unused for console access as requested.
6. If you need to distribute the ground connections to reduce wire length or improve organization, you can use the additional GND pins listed in the "Additional GND Connections" section.
