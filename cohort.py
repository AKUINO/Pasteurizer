#!/usr/bin/python3
# -*- coding: utf-8 -*-
#
# Cohort Module: Sensor time-series management, calibration,
# and fluid tracking along the pasteurization circuit.

import time
import traceback
import csv
import json

import datafiles
import sensor

class Cohort(object):

    TIME = '*'
    VOLUME = '!'

    def __init__(self, periodicity, depth):
        """Initialize the Cohort instance.

        :param periodicity: Time interval in seconds between data samples (e.g., 3s).
        :param depth: Number of periods retained in the rolling buffer (e.g., 100 entries).
        """
        self.periodicity = periodicity  # e.g. 3 seconds interval between cohort data
        self.depth = depth  # e.g. 100 x 3 seconds of data kept
        self.catalog = {}  # Catalog of all sensors in the system with their last values
        self.history = { Cohort.TIME:[None] * self.depth, Cohort.VOLUME:[None] * self.depth }  # Data from sensors {address: [val_0, val_1, ...]}
        self.calibration = {}  # Calibrations of sensors
        self.linear = {}  # Linear regression is preferred
        self.period = 0  # Current index in circular buffer (0 to depth-1)
        self.sequence = []  # Physical sequence of sensors with volume: [[vol_mL, 'address'], ...]
        self.offsetVolume = {}
        self.pumpAddress = None
        self.totalVolume = 0.0
        self.reft = sensor.Sensor(111, 'reft', None)  # Calibration reference data received via Internet

    def addSensor(self, address, sensor_param):
        """Add a sensor to the catalog and initialize its tracking data structures."""
        self.addCatalog(address)
        self.catalog[address] = sensor_param

    def addCatalog(self, address):
        """Prepare memory buffers for a given sensor address."""
        if address not in self.catalog:
            self.catalog[address] = None
            self.history[address] = [None] * self.depth
            self.calibration[address] = []

    def nextPeriod(self,now):
        """log average calibrated sensor values at "now"."""
        for address in self.catalog:
            if self.catalog[address] is not None:
                self.history[address][self.period] = self.getCalibratedValue(
                    address, self.catalog[address].reset() # get current mean value and reset the mean calculation
                )
        self.history[Cohort.TIME][self.period] = now
        if self.pumpAddress is not None and self.pumpAddress in self.history:
            currVol = self.history[self.pumpAddress][self.period]
            if currVol > 0.0: # total pumped volume never goes back because back pumping is inefficient and most heat remains where it arrived
                self.totalVolume += currVol*1000.0 # liters to mL
        self.history[Cohort.VOLUME][self.period] = self.totalVolume
        """Advance one period step in the circular buffer"""
        self.period += 1
        if self.period >= self.depth: # circular buffer, goto beginning
            self.period = 0

    def previous_period(self, per):
        """Return the index of the previous period in the circular buffer."""
        prev = per - 1
        if prev < 0: # circular buffer: reverse to the end
            prev = self.depth - 1
        if prev == self.period:
            return None
        return prev

    def last_period(self):
        """Return the index of the last completed recording period."""
        period = self.period - 1
        if period < 0:
            period = self.depth - 1
        return period

    def dump(self):
        """Print the sequence of sensors, their position and their current value."""
        per = self.last_period()
        print ("%7.3f\" %7.1fmL:" % (self.history[Cohort.TIME][per], self.history[Cohort.VOLUME][per]))
        total = 0
        for entr in self.sequence:
            val = self.history[entr[1]][per]
            total += entr[0]
            print(
                "%2d: [%s] +%6.1fmL %7.5f°C"
                % (per, entr[1], entr[0], val if val else 0.0)
            )
        print(" [TOTAL] =%6.1fmL" % total)

    def last_travel(self, address):
        if not (self.pumpAddress and self.pumpAddress in self.catalog):
            return None, None

        """Reconstruct the thermal history experienced by a fluid slice arriving at a specific sensor."""
        per = self.last_period()
        pseq = 0
        for entr in self.sequence:
            if entr[1] == address:
                break
            pseq += 1

        if pseq >= len(self.sequence):
            # Unknown sensor address
            return None, None

        result = []
        volTotal = 0.0
        while True:
            entr = self.sequence[pseq]
            temp = self.history[entr[1]][per]
            if not temp:
                break
            result.insert(0, [per, entr[1], temp])
            volTube = entr[0]
            volTotal += volTube
            volPer = 0

            while True:
                vol = self.history[self.pumpAddress][per]
                if not vol or vol <= 0:
                    break
                volPer += vol * 1000.0  # Convert L to mL
                if volPer >= volTube:
                    break
                per = self.previous_period(per)
                if per is None:
                    break

            pseq = pseq - 1
            if pseq < 0:
                break

        return volTotal / 1000.0, result

    def diff_time(self, beginPer, endPer):
        """Calculate elapsed time in seconds between two periods."""
        # if endPer >= beginPer:
        #     return (endPer - beginPer) * self.periodicity
        # else:
        #     return (endPer + (self.depth - beginPer)) * self.periodicity
        endTime = self.history[Cohort.TIME][endPer]
        begTime = self.history[Cohort.TIME][beginPer]
        if endTime is not None and begTime is not None:
            return endTime - begTime
        else:
            return None

    def diff_mL(self, beginPer, endPer):
        """Calculate elapsed volume in mL between two periods."""
        endVol = self.history[Cohort.VOLUME][endPer]
        begVol = self.history[Cohort.VOLUME][beginPer]
        if endVol is not None and begVol is not None:
            return endVol - begVol
        else:
            return None

    def evolution(self, begAddr, endAddr):
        """Return the begin+end temperature between a start and arrival point, time spent, and volume transferred."""
        begin = None
        end = None
        begPer = None
        endPer = None
        volTotal, tablo = self.last_travel(endAddr)
        if tablo:
            for line in tablo:
                if line[1] == begAddr:
                    begin = line[2]
                    begPer = line[0]
                if line[1] == endAddr:
                    end = line[2]
                    endPer = line[0]
            if not begin or not end:
                return None, None, None, None
            return volTotal, self.diff_time(begPer, endPer), begin, end
        return None, None, None, None

    def saveCalibration(self, address, means):
        """Save a multi-point calibration table to a tab-separated file."""
        if datafiles is None:
            self.calibration[address] = means
            return
        try:
            with open(datafiles.calibfile(address), "w") as data_file:
                for tuples in means:
                    mean = tuples[1]
                    data_file.write(
                        "%.1f\t%d\t%.3f\t%.3f\n"
                        % (tuples[0], mean[0], mean[1], mean[2])
                    )
            self.calibration[address] = means
        except Exception:
            traceback.print_exc()

    def saveLinear(self, address, a, b):
        """Save linear calibration coefficients (a*x + b) to a JSON file."""
        if datafiles is None:
            self.linear[address] = {'a': a, 'b': b}
            return
        try:
            with open(datafiles.linearfile(address), "w") as data_file:
                obj = {'a': a, 'b': b}
                json.dump(obj, data_file)
        except Exception:
            traceback.print_exc()

    def readCalibration(self, address):
        """Load sensor calibration (prioritizes linear JSON file, falls back to CSV table)."""
        if datafiles is None:
            return
        try:
            with open(datafiles.linearfile(address), "r") as jsonfile:
                self.linear[address] = json.load(jsonfile)
        except FileNotFoundError:
            try:
                with open(datafiles.calibfile(address), "r") as csvfile:
                    reader = csv.DictReader(
                        csvfile, fieldnames=['key', 'qty', 'app', 'tru'], delimiter="\t"
                    )
                    means = []
                    for row in reader:
                        means.append([
                            float(row['key']),
                            [int(row['qty']), float(row['app']), float(row['tru'])],
                        ])
                    self.calibration[address] = means
            except FileNotFoundError:
                print(
                    'No calibration found for sensor "'
                    + address
                    + '" in directory '
                    + datafiles.DIR_DATA_CALIB
                )
            except Exception:
                traceback.print_exc()
        except Exception:
            traceback.print_exc()

    def mergeCalibration(self, current_observ):
        """Merge current calibration into future calibration."""
        return current_observ

    def getLinear(self, address):
        if address in self.linear:
            return self.linear[address]
        else:
            return None

    def getCalibratedValue(self, address, apparentValue=None):
        """Apply calibration (linear regression or piecewise interpolation) to raw value."""
        if address not in self.catalog:
            return None
        if apparentValue is None:
            if self.catalog[address]:
                apparentValue = self.catalog[address].value
        if apparentValue is None:
            return None

        # 1. Linear calibration
        if address in self.linear:
            interpol = self.linear[address]
            trueValue = (float(interpol['a']) * apparentValue) + float(
                interpol['b']
            )
        else:
            trueValue = apparentValue
            # 2. Piecewise linear interpolation
            if address in self.calibration:
                siz = len(self.calibration[address])
                if siz > 0:
                    for i in range(siz):
                        if apparentValue <= self.calibration[address][i][1][1]:
                            if i > 0:
                                p = self.calibration[address][i][1][1] - apparentValue
                                comp_p = (
                                        apparentValue - self.calibration[address][i - 1][1][1]
                                )
                                offset_bottom = (
                                        self.calibration[address][i - 1][1][2]
                                        - self.calibration[address][i - 1][1][1]
                                )
                                offset_top = (
                                        self.calibration[address][i][1][2]
                                        - self.calibration[address][i][1][1]
                                )
                                # Corrected formula: (offset_bottom * comp_p)
                                trueValue = apparentValue + (
                                        ((offset_bottom * comp_p) + (offset_top * p))
                                        / (
                                                self.calibration[address][i][1][1]
                                                - self.calibration[address][i - 1][1][1]
                                        )
                                )
                                break
                            else:
                                trueValue = (
                                        apparentValue
                                        - self.calibration[address][i][1][1]
                                        + self.calibration[address][i][1][2]
                                )
                                break
                        elif i == siz - 1:
                            trueValue = (
                                    apparentValue
                                    - self.calibration[address][i][1][1]
                                    + self.calibration[address][i][1][2]
                            )
                            break
        return trueValue

    def val(self, address, format_param="%.2f", peak=0):
        """Return formatted calibrated string (current, min peak, or max peak)."""
        if address not in self.catalog:
            return ""
        curr_sensor = self.catalog[address]
        if not curr_sensor or curr_sensor.value is None:
            return ""
        else:
            if peak == 0:
                return format_param % self.getCalibratedValue(address)
            elif peak < 0:
                return format_param % self.getCalibratedValue(
                    address, apparentValue=curr_sensor.min
                )
            else:
                return format_param % self.getCalibratedValue(
                    address, apparentValue=curr_sensor.max
                )

    def up_to_mL(self, address1, address2 = None):
        """Return volume (mL) of the section associated with the given sensor address."""
        v1 = 0.0
        if address1 and address1 in self.offsetVolume:
            v1 = self.offsetVolume[address1]
        if address2 and address2 in self.offsetVolume:
            return self.offsetVolume[address2] - v1
        elif v1 > 0.0:
            total = 0.0
            for entr in self.sequence:
                if entr[1] == address1:
                    break
                total += entr[0]
            return v1 - total
        return 0.0

    def setSequence(self, seq):
        self.sequence = seq
        total = 0.0
        for entr in self.sequence:
            total += entr[0]
            self.offsetVolume[entr[1]] = total

    def find_period_by_volume (self, vol):
        per = self.last_period()
        while per is not None:
            curr = self.history[Cohort.VOLUME][per]
            if (curr is not None) and (vol >= curr):
                return per
            per = self.previous_period(per)
        return None

    def display(self, term, address, format_param=" %5.2f°C"):
        """Display calibrated value on terminal with color indicator (blue=drop, red=increase)."""
        if address not in self.catalog:
            return
        curr_sensor = self.catalog[address]
        if curr_sensor.changed < 0.0:
            attr = term.blue
        elif curr_sensor.changed > 0.0:
            attr = term.red
        else:
            attr = term.black
        if curr_sensor.value is not None:
            term.write(
                format_param % self.getCalibratedValue(address), attr, term.bgwhite
            )


# =====================================================================
# UNIT TESTS (USING SIMPLE PRINT STATEMENTS)
# =====================================================================
if __name__ == "__main__":
    print("=== STARTING COHORT UNIT TESTS ===")

    # 1. Initialization Test
    cohort = Cohort(periodicity=3, depth=10)
    print(
        "[TEST 1] Initialization: periodicity=%d, depth=%d"
        % (cohort.periodicity, cohort.depth)
    )

    # 2. Add Sensors
    s_inlet = sensor.Sensor(5, 'sensor_inlet', 'param_inlet')
    s_outlet = sensor.Sensor(5, 'sensor_outlet', 'param_outlet')
    s_warrant = sensor.Sensor(5, 'sensor_warrant', 'param_warrant')
    holding_vol = 450.0
    s_pump = sensor.Sensor(7, 'pump', 'param_pump')

    cohort.addSensor('sensor_inlet', s_inlet)
    cohort.addSensor('sensor_outlet', s_outlet)
    cohort.addSensor('sensor_warrant', s_warrant)
    cohort.addSensor('pump', s_pump)

    print("[TEST 2] Catalog keys:", list(cohort.catalog.keys()))
    print(
        "[TEST 2] History buffer allocated length for sensor_inlet:",
        len(cohort.history['sensor_inlet']),
    )

    # 3. Define Physical Sequence (volume_mL, address)
    cohort.setSequence ( [[500.0, 'sensor_inlet'], [1200.0, 'sensor_outlet'], [800.0, 'sensor_warrant']] )
    cohort.pumpAddress = 'pump'
    print("[TEST 3] Sequence setup:", cohort.sequence)
    print(
        "[TEST 3] Section volume for sensor_outlet (mL):",
        cohort.up_to_mL('sensor_outlet'),
    )
    print(
        "[TEST 3] Cumulative volume up to sensor_outlet (mL):",
        cohort.up_to_mL(None,'sensor_outlet'),
    )

    # 4. Simulate Circular Buffer updates
    print("[TEST 4] Simulating data collection over 15 periods...")
    for step in range(15):
        s_inlet.set(20.0 + step * 0.2)
        s_outlet.set(65.0 + step * 0.25)
        s_warrant.set(71.7 + step * 0.1)
        s_pump.set(0.2)  # 0.2 L per period = 200 mL
        now = time.perf_counter()
        cohort.nextPeriod(now)
        print(
            "  Step %d completed. Current period index: %d" % (step, cohort.period)
        )

    print("[TEST 4] History for sensor_inlet:", cohort.history['sensor_inlet'])
    print("[TEST 4] History for sensor_outlet:", cohort.history['sensor_outlet'])
    print("[TEST 4] History for sensor_warrant:", cohort.history['sensor_warrant'])
    print("[TEST 4] Last completed period index:", cohort.last_period())

    # 5. Test Linear Calibration
    print("[TEST 5] Testing Linear Calibration...")
    cohort.linear['sensor_inlet'] = {'a': 1.05, 'b': -0.5}
    raw_val = 20.0
    cal_val = cohort.getCalibratedValue('sensor_inlet', apparentValue=raw_val)
    expected_val = 1.05 * 20.0 - 0.5
    print(
        "  Raw: %.2f -> Calibrated: %.2f (Expected: %.2f)"
        % (raw_val, cal_val, expected_val)
    )

    # 6. Test Dump
    print("[TEST 6] Testing Dump:")
    cohort.dump()

    # # 7. Test Fluid Travel Tracking
    # print("[TEST 7] Testing last_travel for sensor_outlet:")
    # vol_tot, travel_log = cohort.last_travel('sensor_outlet')
    # print("  Total volume (L):", vol_tot)
    # print("  Travel log entries:", travel_log)
    #
    # print("[TEST 7] Testing evolution from sensor_inlet to sensor_outlet:")
    # vol, dt, beg_temp, end_temp = cohort.evolution(
    #     'sensor_inlet', 'sensor_outlet'
    # )
    # print(
    #     "  Volume: %s L, Time: %s s, Inlet Temp: %s, Outlet Temp: %s"
    #     % (vol, dt, beg_temp, end_temp)
    # )

    print("=== EVALUATING EXCHANGER PERFORMANCE ===")
    """$$\eta (\%) = \frac{T_{\text{préchauffé}} - T_{\text{cru, entrée}}}{T_{\text{pasteurisé, entrée}} - T_{\text{cru, entrée}}} \times 100$$2. Les températures de la section coaxiale (25 m)Pour effectuer ce suivi en continu2 :$T_{\text{cru, entrée}}$ : Température du lait cru froid à l'admission.$T_{\text{préchauffé}}$ : Température du lait cru préchauffé à la sortie de la section coaxiale (juste avant d'entrer dans la cuve de chauffe).$T_{\text{pasteurisé, entrée}}$ : Température du lait chaud qui revient du tube de maintien (ex. 85 °C ou 72 °C) pour entrer dans l'échangeur3.$T_{\text{refroidi, sortie}}$ : Température du lait pasteurisé après son refroidissement à la sortie de la section coaxiale2."""
    Voutlet = cohort.history[cohort.VOLUME][cohort.last_period()]
    if Voutlet:
        Vinlet = Voutlet - cohort.up_to_mL('sensor_inlet','sensor_outlet')
        Vreturn = Voutlet - holding_vol
        Toutlet = cohort.history['sensor_outlet'][cohort.last_period()]
        Tinlet = None
        Treturn = None
        if Toutlet:
            Dinlet = cohort.find_period_by_volume(Vinlet)
            if Dinlet:
                Tinlet = cohort.history['sensor_inlet'][Dinlet]
                Dreturn = cohort.find_period_by_volume(Vreturn)
                if Dreturn:
                    Treturn = cohort.history['sensor_warrant'][Dreturn]
                    print ("In=%5.1f°C, out=%5.1f, ret=%5.1f, Performance = %5.1f"
                           % (Tinlet,Toutlet,Treturn,100.0*(Toutlet-Tinlet)/(Treturn-Tinlet)))

    print("=== COHORT UNIT TESTS COMPLETED SUCCESSFULLY ===")
