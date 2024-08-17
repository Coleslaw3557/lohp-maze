# LoHP Maze Wiring Guide
# UNIT - C (Updated)

## Raspberry Pi Full 40-pin Pinout Connections

| Pin | GPIO | Function | Connection |
|-----|------|----------|------------|
| 1   | 3V3  | Power    | LS1 VCCA, LS2 VCCA, LS1 OE, LS2 OE, ADS1115 VDD, All Buttons VCC |
| 2   | 5V   | Power    | LS1 VCCB, LS2 VCCB, All Laser Module VCC |
| 3   | GPIO2| I2C SDA  | ADS1115 SDA |
| 4   | 5V   | Power    | Not used (available if needed) |
| 5   | GPIO3| I2C SCL  | ADS1115 SCL |
| 6   | GND  | Ground   | LS1 GND, LS2 GND, ADS1115 GND, All Laser Module GND, All Buttons GND |
| 7   | GPIO4| GPIO     | Temple Room LT (via LS1) |
| 8   | GPIO14| UART TXD| Not used (reserved for console access) |
| 9   | GND  | Ground   | Not used (available if needed) |
| 10  | GPIO15| UART RXD| Not used (reserved for console access) |
| 11  | GPIO17| GPIO    | Temple Room LR (via LS1) |
| 12  | GPIO18| GPIO    | Deep Playa Handshake LT (via LS1) |
| 13  | GPIO27| GPIO    | Deep Playa Handshake LR (via LS1) |
| 14  | GND  | Ground   | Not used (available if needed) |
| 15  | GPIO22| GPIO    | Bike Lock Room LT (via LS1) |
| 16  | GPIO23| GPIO    | Bike Lock Room LR (via LS1) |
| 17  | 3V3  | Power    | Not used (available if needed) |
| 18  | GPIO24| GPIO    | Vertical Moop March LT (via LS2) |
| 19  | GPIO10| SPI MOSI| Not used |
| 20  | GND  | Ground   | Not used (available if needed) |
| 21  | GPIO9 | SPI MISO| Not used |
| 22  | GPIO25| GPIO    | Vertical Moop March LR (via LS2) |
| 23  | GPIO11| SPI SCLK| Not used |
| 24  | GPIO8 | SPI CE0 | Not used |
| 25  | GND  | Ground   | Not used (available if needed) |
| 26  | GPIO7 | SPI CE1 | Not used |
| 27  | ID_SD | I2C ID EEPROM | Not used (reserved for HAT ID EEPROM) |
| 28  | ID_SC | I2C ID EEPROM | Not used (reserved for HAT ID EEPROM) |
| 29  | GPIO5 | GPIO    | Monkey Room LT (via LS2) |
| 30  | GND  | Ground   | Not used (available if needed) |
| 31  | GPIO6 | GPIO    | Monkey Room LR (via LS2) |
| 32  | GPIO12| GPIO    | Monkey Room Button |
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
| Temple Room | LT | 7 | 4 | Via LS1 |
| Temple Room | LR | 11 | 17 | Via LS1 |
| Deep Playa Handshake | LT | 12 | 18 | Via LS1 |
| Deep Playa Handshake | LR | 13 | 27 | Via LS1 |
| Bike Lock Room | LT | 15 | 22 | Via LS1 |
| Bike Lock Room | LR | 16 | 23 | Via LS1 |
| Vertical Moop March | LT | 18 | 24 | Via LS2 |
| Vertical Moop March | LR | 22 | 25 | Via LS2 |
| Monkey Room | LT | 29 | 5 | Via LS2 |
| Monkey Room | LR | 31 | 6 | Via LS2 |
| Monkey Room | Button | 32 | 12 | Direct to GPIO |

## Power Connections

| Voltage | Physical Pin | Connections |
|---------|--------------|-------------|
| 3.3V | 1 | LS1 VCCA, LS2 VCCA, LS1 OE, LS2 OE, ADS1115 VDD, All Buttons VCC |
| 5V | 2 | LS1 VCCB, LS2 VCCB, All Laser Module VCC |
| GND | 6 | LS1 GND, LS2 GND, ADS1115 GND, All Laser Module GND, All Buttons GND |

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

### LS1 (Temple Room, Deep Playa Handshake, and Bike Lock Room)

| Pin | Connection |
|-----|------------|
| VCCA | 3.3V (Pi Pin 1) |
| VCCB | 5V (Pi Pin 2) |
| GND | GND (Pi Pin 6) |
| OE | 3.3V (Pi Pin 1) |
| A1 | Raspberry Pi GPIO 4 (Pi Pin 7) |
| B1 | Temple Room LT Signal |
| A2 | Raspberry Pi GPIO 17 (Pi Pin 11) |
| B2 | Temple Room LR Signal |
| A3 | Raspberry Pi GPIO 18 (Pi Pin 12) |
| B3 | Deep Playa Handshake LT Signal |
| A4 | Raspberry Pi GPIO 27 (Pi Pin 13) |
| B4 | Deep Playa Handshake LR Signal |
| A5 | Raspberry Pi GPIO 22 (Pi Pin 15) |
| B5 | Bike Lock Room LT Signal |
| A6 | Raspberry Pi GPIO 23 (Pi Pin 16) |
| B6 | Bike Lock Room LR Signal |
| A7-A8 | Not Connected |
| B7-A8 | Not Connected |

### LS2 (Vertical Moop March and Monkey Room)

| Pin | Connection |
|-----|------------|
| VCCA | 3.3V (Pi Pin 1) |
| VCCB | 5V (Pi Pin 2) |
| GND | GND (Pi Pin 6) |
| OE | 3.3V (Pi Pin 1) |
| A1 | Raspberry Pi GPIO 24 (Pi Pin 18) |
| B1 | Vertical Moop March LT Signal |
| A2 | Raspberry Pi GPIO 25 (Pi Pin 22) |
| B2 | Vertical Moop March LR Signal |
| A3 | Raspberry Pi GPIO 5 (Pi Pin 29) |
| B3 | Monkey Room LT Signal |
| A4 | Raspberry Pi GPIO 6 (Pi Pin 31) |
| B4 | Monkey Room LR Signal |
| A5-A8 | Not Connected |
| B5-B8 | Not Connected |

## ADS1115 ADC

### ADC (Deep Playa Handshake Room)

| Pin | Connection |
|-----|------------|
| VDD | 3.3V (Pi Pin 1) |
| GND | GND (Pi Pin 6) |
| SCL | Raspberry Pi GPIO 3 (Pi Pin 5) |
| SDA | Raspberry Pi GPIO 2 (Pi Pin 3) |
| A0 | Deep Playa Handshake Button 1 |
| A1 | Deep Playa Handshake Button 2 |
| A2 | Deep Playa Handshake Button 3 |
| A3 | Deep Playa Handshake Button 4 |
| A4 | Deep Playa Handshake Button 5 |
| ADDR | GND (Pi Pin 6) (I2C address 0x48) |

## Laser Modules

### Laser Transmitters (LT)

| Room | GPIO | Physical Pin | Connection |
|------|------|--------------|------------|
| Temple Room | 4 | 7 | LS1 B1 |
| Deep Playa Handshake | 18 | 12 | LS1 B3 |
| Bike Lock Room | 22 | 15 | LS1 B5 |
| Vertical Moop March | 24 | 18 | LS2 B1 |
| Monkey Room | 5 | 29 | LS2 B3 |

### Laser Receivers (LR)

| Room | GPIO | Physical Pin | Connection |
|------|------|--------------|------------|
| Temple Room | 17 | 11 | LS1 B2 |
| Deep Playa Handshake | 27 | 13 | LS1 B4 |
| Bike Lock Room | 23 | 16 | LS1 B6 |
| Vertical Moop March | 25 | 22 | LS2 B2 |
| Monkey Room | 6 | 31 | LS2 B4 |

## Button Connections

### Deep Playa Handshake Room

| Button | Connection |
|--------|------------|
| Button 1 | ADC A0 |
| Button 2 | ADC A1 |
| Button 3 | ADC A2 |
| Button 4 | ADC A3 |
| Button 5 | ADC A4 |

### Monkey Room

| Button | GPIO | Physical Pin |
|--------|------|--------------|
| Button | 12 | 32 |

## Additional Notes

1. All laser modules (LT and LR) have their VCC connected to 5V (Pi Pin 2) and GND connected to the main GND (Pi Pin 6).
2. All buttons have their VCC connected to 3.3V (Pi Pin 1) and GND connected to the main GND (Pi Pin 6).
3. The five SPST buttons in the Deep Playa Handshake room are connected to the ADS1115 ADC (channels A0 to A4) to save GPIO pins on the Raspberry Pi.
4. The single SPST button in the Monkey Room is directly connected to GPIO 12 (Physical Pin 32) for simplicity.
5. Ensure all GND connections are properly made to create a common ground for the entire system.
6. Double-check all connections before powering on the Raspberry Pi to prevent any potential damage to the components.
7. The UART pins (GPIO 14 and 15, or physical pins 8 and 10) are left unused for console access as requested.
8. If you need to distribute the ground connections to reduce wire length or improve organization, you can use the additional GND pins listed in the "Additional GND Connections" section.
