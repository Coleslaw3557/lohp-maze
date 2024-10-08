# LoHP Maze Wiring Guide
# UNIT - B
# 192.168.1.186

## Raspberry Pi Full 40-pin Pinout Connections

| Pin | GPIO | Function | Connection |
|-----|------|----------|------------|
| 1   | 3V3  | Power    | LS1 VCCA, LS2 VCCA, LS1 OE, LS2 OE, ADS1115_1 VDD, ADS1115_2 VDD, ADS1115_2 ADDR, All Buttons VCC |
| 2   | 5V   | Power    | LS1 VCCB, LS2 VCCB, All Laser Module VCC |
| 3   | GPIO2| I2C SDA  | ADS1115_1 SDA, ADS1115_2 SDA |
| 4   | 5V   | Power    | Not used (available if needed) |
| 5   | GPIO3| I2C SCL  | ADS1115_1 SCL, ADS1115_2 SCL |
| 6   | GND  | Ground   | LS1 GND, LS2 GND, ADS1115_1 GND, ADS1115_2 GND, ADS1115_1 ADDR, All Laser Module GND, All Buttons GND |
| 7   | GPIO4| GPIO     | Not used |
| 8   | GPIO14| UART TXD| Not used (reserved for console access) |
| 9   | GND  | Ground   | Not used (available if needed) |
| 10  | GPIO15| UART RXD| Not used (reserved for console access) |
| 11  | GPIO17| GPIO    | Cop Dodge LT (via LS1) |
| 12  | GPIO18| GPIO    | Not used |
| 13  | GPIO27| GPIO    | Cop Dodge LR (via LS1) |
| 14  | GND  | Ground   | Not used (available if needed) |
| 15  | GPIO22| GPIO    | Gate LT (via LS1) |
| 16  | GPIO23| GPIO    | Gate LR (via LS1) |
| 17  | 3V3  | Power    | Not used (available if needed) |
| 18  | GPIO24| GPIO    | Guy Line LT (via LS2) |
| 19  | GPIO10| SPI MOSI| Not used |
| 20  | GND  | Ground   | Not used (available if needed) |
| 21  | GPIO9 | SPI MISO| Not used |
| 22  | GPIO25| GPIO    | Guy Line LR (via LS2) |
| 23  | GPIO11| SPI SCLK| Not used |
| 24  | GPIO8 | SPI CE0 | Not used |
| 25  | GND  | Ground   | Not used (available if needed) |
| 26  | GPIO7 | SPI CE1 | Not used |
| 27  | ID_SD | I2C ID EEPROM | Not used (reserved for HAT ID EEPROM) |
| 28  | ID_SC | I2C ID EEPROM | Not used (reserved for HAT ID EEPROM) |
| 29  | GPIO5 | GPIO    | Sparkle Pony LT (via LS2) |
| 30  | GND  | Ground   | Not used (available if needed) |
| 31  | GPIO6 | GPIO    | Sparkle Pony LR (via LS2) |
| 32  | GPIO12| GPIO    | Not used |
| 33  | GPIO13| GPIO    | Porto LT (via LS2) |
| 34  | GND  | Ground   | Not used (available if needed) |
| 35  | GPIO19| GPIO    | Porto LR (via LS2) |
| 36  | GPIO16| GPIO    | Not used |
| 37  | GPIO26| GPIO    | Not used |
| 38  | GPIO20| GPIO    | Not used |
| 39  | GND  | Ground   | Not used (available if needed) |
| 40  | GPIO21| GPIO    | Not used |

## Raspberry Pi GPIO Connections

| Room | Component | Physical Pin | GPIO | Connection |
|------|-----------|--------------|------|------------|
| All | I2C SDA | 3 | 2 | ADS1115_1 SDA, ADS1115_2 SDA |
| All | I2C SCL | 5 | 3 | ADS1115_1 SCL, ADS1115_2 SCL |
| Cop Dodge | LT | 11 | 17 | Via LS1 |
| Cop Dodge | LR | 13 | 27 | Via LS1 |
| Gate | LT | 15 | 22 | Via LS1 |
| Gate | LR | 16 | 23 | Via LS1 |
| Guy Line | LT | 18 | 24 | Via LS2 |
| Guy Line | LR | 22 | 25 | Via LS2 |
| Sparkle Pony | LT | 29 | 5 | Via LS2 |
| Sparkle Pony | LR | 31 | 6 | Via LS2 |
| Porto | LT | 33 | 13 | Via LS2 |
| Porto | LR | 35 | 19 | Via LS2 |

## Power Connections

| Voltage | Physical Pin | Connections |
|---------|--------------|-------------|
| 3.3V | 1 | LS1 VCCA, LS2 VCCA, LS1 OE, LS2 OE, ADS1115_1 VDD, ADS1115_2 VDD, ADS1115_2 ADDR, All Buttons VCC |
| 5V | 2 | LS1 VCCB, LS2 VCCB, All Laser Module VCC |
| GND | 6 | LS1 GND, LS2 GND, ADS1115_1 GND, ADS1115_2 GND, ADS1115_1 ADDR, All Laser Module GND, All Buttons GND |

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

### LS1 (Cop Dodge and Gate Rooms)

| Pin | Connection |
|-----|------------|
| VCCA | 3.3V (Pi Pin 1) |
| VCCB | 5V (Pi Pin 2) |
| GND | GND (Pi Pin 6) |
| OE | 3.3V (Pi Pin 1) |
| A1 | Raspberry Pi GPIO 17 (Pi Pin 11) |
| B1 | Cop Dodge LT Signal |
| A2 | Raspberry Pi GPIO 27 (Pi Pin 13) |
| B2 | Cop Dodge LR Signal |
| A3 | Raspberry Pi GPIO 22 (Pi Pin 15) |
| B3 | Gate LT Signal |
| A4 | Raspberry Pi GPIO 23 (Pi Pin 16) |
| B4 | Gate LR Signal |
| A5-A8 | Not Connected |
| B5-B8 | Not Connected |

### LS2 (Guy Line, Sparkle Pony, and Porto Rooms)

| Pin | Connection |
|-----|------------|
| VCCA | 3.3V (Pi Pin 1) |
| VCCB | 5V (Pi Pin 2) |
| GND | GND (Pi Pin 6) |
| OE | 3.3V (Pi Pin 1) |
| A1 | Raspberry Pi GPIO 24 (Pi Pin 18) |
| B1 | Guy Line LT Signal |
| A2 | Raspberry Pi GPIO 25 (Pi Pin 22) |
| B2 | Guy Line LR Signal |
| A3 | Raspberry Pi GPIO 5 (Pi Pin 29) |
| B3 | Sparkle Pony LT Signal |
| A4 | Raspberry Pi GPIO 6 (Pi Pin 31) |
| B4 | Sparkle Pony LR Signal |
| A5 | Raspberry Pi GPIO 13 (Pi Pin 33) |
| B5 | Porto LT Signal |
| A6 | Raspberry Pi GPIO 19 (Pi Pin 35) |
| B6 | Porto LR Signal |
| A7-A8 | Not Connected |
| B7-B8 | Not Connected |

## ADS1115 ADCs

### ADC1 (Buttons 1-4)

| Pin | Connection | Terminal Block ID |
|-----|------------|-------------------|
| VDD | 3.3V (Pi Pin 1) | |
| GND | GND (Pi Pin 6) | |
| SCL | Raspberry Pi GPIO 3 (Pi Pin 5) | |
| SDA | Raspberry Pi GPIO 2 (Pi Pin 3) | |
| A0 | Button 1 Signal | Green - 1 |
| A1 | Button 2 Signal | Green - 2 |
| A2 | Button 3 Signal | Pi Gray - 1 |
| A3 | Button 4 Signal | Pi Gray - 2 |
| ADDR | GND (Pi Pin 6) (I2C address 0x48) | |

### ADC2 (Buttons 5-6)

| Pin | Connection | Terminal Block ID |
|-----|------------|-------------------|
| VDD | 3.3V (Pi Pin 1) | |
| GND | GND (Pi Pin 6) | |
| SCL | Raspberry Pi GPIO 3 (Pi Pin 5) | |
| SDA | Raspberry Pi GPIO 2 (Pi Pin 3) | |
| A0 | Button 5 Signal | Pi - 4 |
| A1 | Button 6 Signal | 5 |
| A2 | Not Connected | 6 |
| A3 | Not Connected | 3 (Unused) |
| ADDR | VDD (Pi Pin 1) (I2C address 0x49) | |

## Laser Modules

### Laser Transmitters (LT)

| Room | GPIO | Physical Pin | Connection | Terminal Block ID |
|------|------|--------------|------------|-------------------|
| Cop Dodge | 17 | 11 | LS1 B1 | Green 3 |
| Gate | 22 | 15 | LS1 B3 | Green 5 |
| Guy Line | 24 | 18 | LS2 B1 | Green 7 |
| Sparkle Pony | 5 | 29 | LS2 B3 | Green 8 |
| Porto | 13 | 33 | LS2 B5 | Green 11 |

### Laser Receivers (LR)

| Room | GPIO | Physical Pin | Connection | Terminal Block ID |
|------|------|--------------|------------|-------------------|
| Cop Dodge | 27 | 13 | LS1 B2 | Green 4 |
| Gate | 23 | 16 | LS1 B4 | Green 6 |
| Guy Line | 25 | 22 | LS2 B2 | Green 8 |
| Sparkle Pony | 6 | 31 | LS2 B4 | Green 10 |
| Porto | 19 | 35 | LS2 B6 | Green 12 |

## Button Connections

| Button | ADC Connection | Terminal Block ID |
|--------|----------------|-------------------|
| Button 1 | ADC1 A0 | Green - 1 |
| Button 2 | ADC1 A1 | Green - 2 |
| Button 3 | ADC1 A2 | Pi Gray - 1 |
| Button 4 | ADC1 A3 | Pi Gray - 2 |
| Button 5 | ADC2 A0 | Pi - 4 |
| Button 6 | ADC2 A1 | 5 |

## Additional Notes

1. All laser modules (LT and LR) have their VCC connected to 5V (Pi Pin 2) and GND connected to the main GND (Pi Pin 6).
2. All buttons have their VCC connected to 3.3V (Pi Pin 1) and GND connected to the main GND (Pi Pin 6).
3. All six SPST buttons are now connected directly to ADC channels to save GPIO pins on the Raspberry Pi.
4. Ensure all GND connections are properly made to create a common ground for the entire system.
5. Double-check all connections before powering on the Raspberry Pi to prevent any potential damage to the components.
6. The UART pins (GPIO 14 and 15, or physical pins 8 and 10) are left unused for console access as requested.
7. If you need to distribute the ground connections to reduce wire length or improve organization, you can use the additional GND pins listed in the "Additional GND Connections" section.
8. GPIO 18 (Pi Pin 12) and GPIO 12 (Pi Pin 32) are now unused and available for future expansion if needed.
9. The software will need to be updated to read all button states from the ADC channels instead of GPIO inputs for Buttons 5 and 6.
10. Regularly check the ADC connections to ensure they remain secure, as these are now critical for all button inputs.