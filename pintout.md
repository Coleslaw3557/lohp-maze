Terminal Block:
1.  5V (Red)           [7 wires: 5 Laser Tx, 5 Laser Rx, 1 ADS1115_1, 1 ADS1115_2]
2.  3.3V (Orange)      [5 wires: 2 Resistor Ladders, 3 Piezo Sensors, 1 ADS1115_2 ADDR]
3.  GND (Black)        [15 wires: 5 Laser Tx, 5 Laser Rx, 2 Resistor Ladders, 3 Piezo Sensors, 2 ADS1115s, 1 FTDI]
4.  GPIO 17 (Cop Dodge Tx)  [1 wire]
5.  GPIO 27 (Cop Dodge Rx)  [1 wire]
6.  GPIO 22 (Gate Tx)       [1 wire]
7.  GPIO 5  (Gate Rx)       [1 wire]
8.  GPIO 24 (Guy Line Tx)   [1 wire]
9.  GPIO 6  (Guy Line Rx)   [1 wire]
10. GPIO 25 (Sparkle Pony Tx) [1 wire]
11. GPIO 13 (Sparkle Pony Rx) [1 wire]
12. GPIO 19 (Porto Tx)      [1 wire]
13. GPIO 26 (Porto Rx)      [1 wire]
14. GPIO 2 (SDA)            [2 wires: ADS1115_1, ADS1115_2]
15. GPIO 3 (SCL)            [2 wires: ADS1115_1, ADS1115_2]
16. ADS1115_1 A0            [1 wire: Gate Room Resistor Ladder 1]
17. ADS1115_1 A1            [1 wire: Gate Room Resistor Ladder 2]
18. ADS1115_2 A0            [1 wire: Porto Room Piezo Sensor 1]
19. ADS1115_2 A1            [1 wire: Porto Room Piezo Sensor 2]
20. ADS1115_2 A2            [1 wire: Porto Room Piezo Sensor 3]
21. GPIO 14 (UART TX)       [1 wire: FTDI RX]
22. GPIO 15 (UART RX)       [1 wire: FTDI TX]

[Raspberry Pi] <---> [Terminal Block] <---> [Peripherals]

[ADS1115_1]
  |-- VDD  --> Terminal 1 (5V)
  |-- GND  --> Terminal 3 (GND)
  |-- SDA  --> Terminal 14 (GPIO 2)
  |-- SCL  --> Terminal 15 (GPIO 3)
  |-- ADDR --> Terminal 3 (GND)
  |-- A0   --> Terminal 16
  |-- A1   --> Terminal 17

[ADS1115_2]
  |-- VDD  --> Terminal 1 (5V)
  |-- GND  --> Terminal 3 (GND)
  |-- SDA  --> Terminal 14 (GPIO 2)
  |-- SCL  --> Terminal 15 (GPIO 3)
  |-- ADDR --> Terminal 2 (3.3V)
  |-- A0   --> Terminal 18
  |-- A1   --> Terminal 19
  |-- A2   --> Terminal 20

[FTDI]
  |-- RX   --> Terminal 21 (GPIO 14)
  |-- TX   --> Terminal 22 (GPIO 15)
  |-- GND  --> Terminal 3 (GND)
