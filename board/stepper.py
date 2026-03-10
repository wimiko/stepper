#!/usr/bin/env python3
"""
WiFi Stepper Motor Controller - SKiDL Schematic
================================================
Wemos S2 Mini (ESP32-S2) -> TMC2209 stepper driver -> NEMA 17 motor
Controlled over MQTT from a Raspberry Pi.

Components:
  U1 - Wemos S2 Mini (ESP32-S2 dev board)
  U2 - BTT TMC2209 V1.3 silent stepper driver module
  R1 - 1kOhm UART half-duplex isolation resistor
  C1 - 100uF electrolytic bulk decoupling on 24V rail
  C2 - 100nF ceramic HF decoupling on 24V rail
  J1 - 24V power input (2-pin screw terminal)
  J2 - Motor connector (4-pin screw terminal, NEMA 17)

Version: 1.0
"""

import os
import sys

# Set KiCad symbol library path for flatpak installation before importing skidl
KICAD_SYM_DIR = (
    "/var/lib/flatpak/runtime/org.kicad.kicad.Library/x86_64/stable/"
    "d73f4b58ab0417714762e97bb506b98e2a308f28281e3b70d0ca2863aad637d9/"
    "files/symbols"
)
os.environ["KICAD_SYMBOL_DIR"] = KICAD_SYM_DIR

from skidl import *

lib_search_paths[KICAD].append(KICAD_SYM_DIR)


# =============================================================================
# Custom part definitions for modules
# =============================================================================

def wemos_s2_mini():
    """
    Wemos S2 Mini (ESP32-S2) development board module.

    Represented as a custom part with only the pins used in this design.
    The physical module has 2x 16-pin headers (2.54mm pitch).
    Pin numbering follows the Wemos S2 Mini pinout.
    """
    return Part(
        tool=SKIDL,
        name="Wemos_S2_Mini",
        ref_prefix="U",
        footprint="Connector_PinHeader_2.54mm:PinHeader_2x08_P2.54mm_Vertical",
        pins=[
            Pin(num=1,  name="5V",     func=Pin.types.PWRIN),
            Pin(num=2,  name="3V3",    func=Pin.types.PWROUT),
            Pin(num=3,  name="GND",    func=Pin.types.PWRIN),
            Pin(num=4,  name="GPIO10", func=Pin.types.OUTPUT),
            Pin(num=5,  name="GPIO11", func=Pin.types.OUTPUT),
            Pin(num=6,  name="GPIO12", func=Pin.types.OUTPUT),
            Pin(num=7,  name="GPIO17", func=Pin.types.OUTPUT),   # UART TX
            Pin(num=8,  name="GPIO18", func=Pin.types.INPUT),    # UART RX
            # Remaining header pins as NC placeholders for the footprint
            Pin(num=9,  name="NC1",    func=Pin.types.NOCONNECT),
            Pin(num=10, name="NC2",    func=Pin.types.NOCONNECT),
            Pin(num=11, name="NC3",    func=Pin.types.NOCONNECT),
            Pin(num=12, name="NC4",    func=Pin.types.NOCONNECT),
            Pin(num=13, name="NC5",    func=Pin.types.NOCONNECT),
            Pin(num=14, name="NC6",    func=Pin.types.NOCONNECT),
            Pin(num=15, name="NC7",    func=Pin.types.NOCONNECT),
            Pin(num=16, name="NC8",    func=Pin.types.NOCONNECT),
        ],
    )


def tmc2209_module():
    """
    BTT TMC2209 V1.3 SilentStepStick stepper driver module.

    Pin numbering follows the typical BTT TMC2209 breakout board:
    Left side (1-8):  EN, MS1, MS2, PDN_UART, -, STEP, DIR, VIO
    Right side (9-16): VM, GND, M2B, M2A, M1A, M1B, -, GND
    """
    return Part(
        tool=SKIDL,
        name="TMC2209_BTT",
        ref_prefix="U",
        footprint="Connector_PinHeader_2.54mm:PinHeader_2x08_P2.54mm_Vertical",
        pins=[
            # Left side
            Pin(num=1,  name="EN",       func=Pin.types.INPUT),
            Pin(num=2,  name="MS1",      func=Pin.types.INPUT),
            Pin(num=3,  name="MS2",      func=Pin.types.INPUT),
            Pin(num=4,  name="PDN_UART", func=Pin.types.BIDIR),
            Pin(num=5,  name="NC_L",     func=Pin.types.NOCONNECT),
            Pin(num=6,  name="STEP",     func=Pin.types.INPUT),
            Pin(num=7,  name="DIR",      func=Pin.types.INPUT),
            Pin(num=8,  name="VIO",      func=Pin.types.PWRIN),
            # Right side
            Pin(num=9,  name="VM",       func=Pin.types.PWRIN),
            Pin(num=10, name="GND",      func=Pin.types.PWRIN),
            Pin(num=11, name="M2B",      func=Pin.types.OUTPUT),
            Pin(num=12, name="M2A",      func=Pin.types.OUTPUT),
            Pin(num=13, name="M1A",      func=Pin.types.OUTPUT),
            Pin(num=14, name="M1B",      func=Pin.types.OUTPUT),
            Pin(num=15, name="NC_R",     func=Pin.types.NOCONNECT),
            Pin(num=16, name="GND2",     func=Pin.types.PWRIN),
        ],
    )


# =============================================================================
# Main circuit
# =============================================================================

def main():
    # -------------------------------------------------------------------------
    # Power nets
    # -------------------------------------------------------------------------
    vcc_24v = Net("+24V")
    vcc_24v.drive = POWER

    vcc_5v = Net("+5V")
    vcc_5v.drive = POWER

    vcc_3v3 = Net("+3V3")
    vcc_3v3.drive = POWER

    gnd = Net("GND")
    gnd.drive = POWER

    # -------------------------------------------------------------------------
    # Signal nets
    # -------------------------------------------------------------------------
    step_net     = Net("STEP")
    dir_net      = Net("DIR")
    en_net       = Net("EN")
    uart_tx_net  = Net("UART_TX")
    pdn_uart_net = Net("PDN_UART")

    # Motor phase nets
    m1a_net = Net("M1A")
    m1b_net = Net("M1B")
    m2a_net = Net("M2A")
    m2b_net = Net("M2B")

    # -------------------------------------------------------------------------
    # U1 - Wemos S2 Mini (ESP32-S2 WiFi microcontroller)
    # -------------------------------------------------------------------------
    u1 = wemos_s2_mini()
    u1.ref = "U1"
    u1.value = "Wemos_S2_Mini"

    u1["5V"]     += vcc_5v       # Powered from 5V rail
    u1["3V3"]    += vcc_3v3      # 3.3V output from onboard regulator
    u1["GND"]    += gnd
    u1["GPIO10"] += step_net     # STEP signal to TMC2209
    u1["GPIO11"] += dir_net      # DIR signal to TMC2209
    u1["GPIO12"] += en_net       # EN signal to TMC2209
    u1["GPIO17"] += uart_tx_net  # UART TX -> through R1 for half-duplex
    u1["GPIO18"] += pdn_uart_net # UART RX <- shared PDN_UART bus

    # -------------------------------------------------------------------------
    # R1 - 1kOhm UART half-duplex isolation resistor
    #
    # The TMC2209 uses a single-wire (half-duplex) UART interface on PDN_UART.
    # R1 isolates the ESP32 TX pin from the shared bus so TX and RX can share
    # the same PDN_UART line without bus contention.
    # -------------------------------------------------------------------------
    r1 = Part("Device", "R", value="1k", footprint="Resistor_SMD:R_0805_2012Metric")
    r1.ref = "R1"

    r1[1] += uart_tx_net   # From ESP32 TX (GPIO17)
    r1[2] += pdn_uart_net  # To TMC2209 PDN_UART and ESP32 RX (GPIO18)

    # -------------------------------------------------------------------------
    # U2 - BTT TMC2209 V1.3 stepper driver module
    # -------------------------------------------------------------------------
    u2 = tmc2209_module()
    u2.ref = "U2"
    u2.value = "TMC2209_BTT_V1.3"

    u2["VIO"]      += vcc_3v3      # Logic level reference (3.3V)
    u2["GND"]      += gnd
    u2["GND2"]     += gnd          # Second ground pin
    u2["EN"]       += en_net       # Enable (directly from ESP32)
    u2["STEP"]     += step_net     # Step pulses
    u2["DIR"]      += dir_net      # Direction
    u2["PDN_UART"] += pdn_uart_net # UART interface (half-duplex)
    u2["MS1"]      += gnd          # MS1=GND, MS2=GND -> UART address 0b00
    u2["MS2"]      += gnd          # (required for single-driver UART config)
    u2["VM"]       += vcc_24v      # Motor power supply (24V)

    # Motor phase outputs
    u2["M1A"] += m1a_net
    u2["M1B"] += m1b_net
    u2["M2A"] += m2a_net
    u2["M2B"] += m2b_net

    # -------------------------------------------------------------------------
    # J1 - 24V power input (2-pin screw terminal)
    # -------------------------------------------------------------------------
    j1 = Part(
        "Connector_Generic", "Conn_01x02",
        footprint="TerminalBlock:TerminalBlock_bornier-2_P5.08mm",
        value="24V_IN",
    )
    j1.ref = "J1"

    j1[1] += vcc_24v
    j1[2] += gnd

    # -------------------------------------------------------------------------
    # J2 - Motor connector (4-pin screw terminal for NEMA 17)
    # -------------------------------------------------------------------------
    j2 = Part(
        "Connector_Generic", "Conn_01x04",
        footprint="TerminalBlock:TerminalBlock_bornier-4_P5.08mm",
        value="MOTOR",
    )
    j2.ref = "J2"

    j2[1] += m1a_net  # Coil A+
    j2[2] += m1b_net  # Coil A-
    j2[3] += m2a_net  # Coil B+
    j2[4] += m2b_net  # Coil B-

    # -------------------------------------------------------------------------
    # C1 - 100uF electrolytic bulk decoupling on 24V motor supply
    #
    # Required by TMC2209 datasheet to handle current spikes from the motor
    # driver. Place close to TMC2209 VM pin.
    # -------------------------------------------------------------------------
    c1 = Part(
        "Device", "C_Polarized",
        value="100uF",
        footprint="Capacitor_THT:CP_Radial_D8.0mm_P3.50mm",
    )
    c1.ref = "C1"

    c1[1] += vcc_24v  # Positive
    c1[2] += gnd      # Negative

    # -------------------------------------------------------------------------
    # C2 - 100nF ceramic HF decoupling on 24V motor supply
    #
    # Filters high-frequency switching noise from the TMC2209 driver.
    # Place as close to VM and GND pins as possible.
    # -------------------------------------------------------------------------
    c2 = Part(
        "Device", "C",
        value="100nF",
        footprint="Capacitor_SMD:C_0805_2012Metric",
    )
    c2.ref = "C2"

    c2[1] += vcc_24v
    c2[2] += gnd

    # -------------------------------------------------------------------------
    # Run ERC and generate output
    # -------------------------------------------------------------------------
    ERC()

    # Generate KiCad netlist
    generate_netlist(file_="/home/wim/projects/stepper/board/stepper.net")
    print("\nNetlist generated: /home/wim/projects/stepper/board/stepper.net")


if __name__ == "__main__":
    main()
