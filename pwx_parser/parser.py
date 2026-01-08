#!/usr/bin/env python3
"""
GRAVEL GOD PWX Parser v1.0
Endurance Cycling Coaching Analysis System

Parses PWX files to extract:
- Variability Index (VI)
- Aerobic Decoupling
- Power curve metrics
- Training Stress Score (TSS)
- Intensity Factor (IF)
- Zone distribution

Author: Claude (Anthropic)
License: MIT
"""

import json
import os
import csv
import xml.etree.ElementTree as ET
from datetime import datetime
from pathlib import Path
from statistics import mean, stdev
import logging

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class PWXParser:
    """Parse PWX (PowerTap XML) files and extract training metrics"""

    # Garmin/PowerTap namespaces
    NAMESPACES = {
        'pwx': 'http://www.peaksware.com/PWX/1/0',
        'td': 'http://www.garmin.com/xmlschemas/TrainingCenterDatabase/v2',
        'ns2': 'http://www.garmin.com/xmlschemas/ActivityExtension/v2'
    }

    def __init__(self, ftp=250, lthr=170):
        self.ftp = ftp
        self.lthr = lthr

    def parse_file(self, filepath):
        """Parse single PWX file"""
        try:
            tree = ET.parse(filepath)
            root = tree.getroot()

            trackpoints = []

            # Try PWX format first (PowerTap native)
            for sample in root.findall('.//{http://www.peaksware.com/PWX/1/0}sample'):
                trackpoint = self._extract_pwx_sample(sample)
                if trackpoint['power'] is not None:
                    trackpoints.append(trackpoint)

            # If no PWX data, try TCX format (Garmin)
            if not trackpoints:
                for tp in root.findall('.//td:Trackpoint', self.NAMESPACES):
                    trackpoint = self._extract_tcx_trackpoint(tp)
                    if trackpoint['power'] is not None:
                        trackpoints.append(trackpoint)

            # Also try without namespace (some PWX files)
            if not trackpoints:
                for sample in root.findall('.//sample'):
                    trackpoint = self._extract_pwx_sample_no_ns(sample)
                    if trackpoint['power'] is not None:
                        trackpoints.append(trackpoint)

            if not trackpoints:
                logger.warning(f"No power data in {filepath}")
                return None

            return trackpoints

        except Exception as e:
            logger.error(f"Error parsing {filepath}: {e}")
            return None

    def _extract_pwx_sample(self, sample):
        """Extract data from PWX sample element"""
        ns = '{http://www.peaksware.com/PWX/1/0}'

        power = None
        pwr_elem = sample.find(f'{ns}pwr')
        if pwr_elem is not None and pwr_elem.text:
            try:
                power = int(float(pwr_elem.text))
            except ValueError:
                pass

        hr = None
        hr_elem = sample.find(f'{ns}hr')
        if hr_elem is not None and hr_elem.text:
            try:
                hr = int(float(hr_elem.text))
            except ValueError:
                pass

        cadence = None
        cad_elem = sample.find(f'{ns}cad')
        if cad_elem is not None and cad_elem.text:
            try:
                cadence = int(float(cad_elem.text))
            except ValueError:
                pass

        time_offset = None
        time_elem = sample.find(f'{ns}timeoffset')
        if time_elem is not None and time_elem.text:
            try:
                time_offset = float(time_elem.text)
            except ValueError:
                pass

        return {
            'time': time_offset,
            'power': power,
            'hr': hr,
            'cadence': cadence
        }

    def _extract_pwx_sample_no_ns(self, sample):
        """Extract data from PWX sample without namespace"""
        power = None
        pwr_elem = sample.find('pwr')
        if pwr_elem is not None and pwr_elem.text:
            try:
                power = int(float(pwr_elem.text))
            except ValueError:
                pass

        hr = None
        hr_elem = sample.find('hr')
        if hr_elem is not None and hr_elem.text:
            try:
                hr = int(float(hr_elem.text))
            except ValueError:
                pass

        cadence = None
        cad_elem = sample.find('cad')
        if cad_elem is not None and cad_elem.text:
            try:
                cadence = int(float(cad_elem.text))
            except ValueError:
                pass

        return {
            'time': None,
            'power': power,
            'hr': hr,
            'cadence': cadence
        }

    def _extract_tcx_trackpoint(self, tp):
        """Extract data from TCX Trackpoint element"""
        ns = self.NAMESPACES

        # Power (from Extensions)
        power = None
        watts_elem = tp.find('td:Extensions/ns2:TPX/ns2:Watts', ns)
        if watts_elem is not None:
            try:
                power = int(watts_elem.text)
            except ValueError:
                pass

        # Heart Rate
        hr = None
        hr_elem = tp.find('td:HeartRateBpm/td:Value', ns)
        if hr_elem is not None:
            try:
                hr = int(hr_elem.text)
            except ValueError:
                pass

        # Time
        time_str = None
        time_elem = tp.find('td:Time', ns)
        if time_elem is not None:
            time_str = time_elem.text

        # Cadence
        cadence = None
        cadence_elem = tp.find('td:Cadence', ns)
        if cadence_elem is not None:
            try:
                cadence = int(cadence_elem.text)
            except ValueError:
                pass

        return {
            'time': time_str,
            'power': power,
            'hr': hr,
            'cadence': cadence
        }

    def calculate_metrics(self, trackpoints):
        """Calculate all training metrics from trackpoints"""
        power_values = [tp['power'] for tp in trackpoints if tp['power'] is not None and tp['power'] > 0]
        hr_values = [tp['hr'] for tp in trackpoints if tp['hr'] is not None and tp['hr'] > 0]
        cadence_values = [tp['cadence'] for tp in trackpoints if tp['cadence'] is not None and tp['cadence'] > 0]

        if not power_values:
            return None

        # Basic metrics
        avg_power = mean(power_values)
        max_power = max(power_values)
        duration_seconds = len(power_values)

        # Normalized Power
        np_value = self._calculate_np(power_values)
        if np_value is None:
            np_value = avg_power  # Fallback

        # Variability Index
        vi = np_value / avg_power if avg_power > 0 else None

        # Intensity Factor
        if_value = np_value / self.ftp

        # Training Stress Score
        tss = (duration_seconds * np_value * if_value) / (self.ftp * 3600) * 100

        # Aerobic Decoupling
        decoupling = self._calculate_decoupling(power_values, hr_values) if hr_values else None

        # Zone distribution
        zones = self._calculate_zones(power_values)

        # Avg HR
        avg_hr = mean(hr_values) if hr_values else None
        max_hr = max(hr_values) if hr_values else None

        # Avg Cadence
        avg_cadence = mean(cadence_values) if cadence_values else None

        # Power standard deviation (consistency metric)
        power_stdev = stdev(power_values) if len(power_values) > 1 else 0

        return {
            'duration_seconds': duration_seconds,
            'duration_minutes': round(duration_seconds / 60, 1),
            'avg_power': round(avg_power, 1),
            'max_power': max_power,
            'np': round(np_value, 1),
            'if': round(if_value, 3),
            'vi': round(vi, 3) if vi else None,
            'tss': round(tss, 1),
            'decoupling_pct': round(decoupling, 1) if decoupling else None,
            'avg_hr': round(avg_hr, 1) if avg_hr else None,
            'max_hr': max_hr if max_hr else None,
            'avg_cadence': round(avg_cadence, 1) if avg_cadence else None,
            'power_stdev': round(power_stdev, 1),
            'z1_seconds': zones[1],
            'z2_seconds': zones[2],
            'z3_seconds': zones[3],
            'z4_seconds': zones[4],
            'z5_seconds': zones[5],
            'z6_seconds': zones[6],
            'z7_seconds': zones[7],
            'z1_pct': round(zones[1] / duration_seconds * 100, 1),
            'z2_pct': round(zones[2] / duration_seconds * 100, 1),
            'z3_pct': round(zones[3] / duration_seconds * 100, 1),
            'z4_pct': round(zones[4] / duration_seconds * 100, 1),
            'z5_pct': round(zones[5] / duration_seconds * 100, 1),
            'z6_pct': round(zones[6] / duration_seconds * 100, 1),
            'z7_pct': round(zones[7] / duration_seconds * 100, 1),
        }

    def _calculate_np(self, power_values):
        """Calculate Normalized Power (rolling 30-sec average, 4th power mean)"""
        if len(power_values) < 30:
            return mean(power_values)  # Fallback for short efforts

        rolling = []
        for i in range(len(power_values) - 29):
            rolling.append(mean(power_values[i:i+30]))

        try:
            np_val = sum(p**4 for p in rolling) / len(rolling)
            return np_val ** 0.25
        except Exception as e:
            logger.error(f"Error calculating NP: {e}")
            return None

    def _calculate_decoupling(self, power_values, hr_values):
        """Aerobic Decoupling: HR:Power ratio degradation"""
        if len(power_values) < 2 or len(hr_values) < 2:
            return None

        if len(power_values) != len(hr_values):
            # Trim to same length
            min_len = min(len(power_values), len(hr_values))
            power_values = power_values[:min_len]
            hr_values = hr_values[:min_len]

        mid = len(power_values) // 2

        first_half_power = mean(power_values[:mid])
        first_half_hr = mean(hr_values[:mid])
        ef1 = first_half_power / first_half_hr if first_half_hr > 0 else None

        second_half_power = mean(power_values[mid:])
        second_half_hr = mean(hr_values[mid:])
        ef2 = second_half_power / second_half_hr if second_half_hr > 0 else None

        if ef1 and ef2 and ef1 > 0:
            return ((ef1 - ef2) / ef1) * 100
        return None

    def _calculate_zones(self, power_values):
        """Calculate time in each power zone (Coggan zones)"""
        zones = {1: 0, 2: 0, 3: 0, 4: 0, 5: 0, 6: 0, 7: 0}

        for p in power_values:
            pct = (p / self.ftp) * 100
            if pct < 55:
                zones[1] += 1  # Active Recovery
            elif pct < 76:
                zones[2] += 1  # Endurance
            elif pct < 91:
                zones[3] += 1  # Tempo
            elif pct < 106:
                zones[4] += 1  # Threshold
            elif pct < 121:
                zones[5] += 1  # VO2max
            elif pct < 151:
                zones[6] += 1  # Anaerobic
            else:
                zones[7] += 1  # Neuromuscular

        return zones


def load_config(config_file='config.json'):
    """Load athlete config (FTP, LTHR, etc.)"""
    if os.path.exists(config_file):
        with open(config_file) as f:
            return json.load(f)

    # Default config
    return {
        'athlete': {
            'name': 'Athlete',
            'ftp': 250,
            'lthr': 170,
            'max_hr': 185,
            'weight_kg': 75
        },
        'analysis': {
            'vi_threshold_good': 1.05,
            'vi_threshold_acceptable': 1.10,
            'decoupling_threshold_good': 5.0,
            'decoupling_threshold_warning': 10.0,
            'tss_per_week_target': 500
        }
    }


def process_pwx_folder(pwx_folder='./pwx_files', output_folder='./output', config_file='config.json'):
    """Process all PWX files in folder"""

    config = load_config(config_file)
    athlete_config = config.get('athlete', config)
    parser = PWXParser(
        ftp=athlete_config.get('ftp', 250),
        lthr=athlete_config.get('lthr', 170)
    )

    pwx_folder = Path(pwx_folder)
    output_folder = Path(output_folder)
    output_folder.mkdir(exist_ok=True)

    # Support both .pwx and .tcx files
    pwx_files = sorted(list(pwx_folder.glob('*.pwx')) + list(pwx_folder.glob('*.tcx')))

    if not pwx_files:
        logger.warning(f"No PWX/TCX files found in {pwx_folder}")
        return []

    logger.info(f"Processing {len(pwx_files)} files from {pwx_folder}")

    results = []
    errors = []

    for pwx_file in pwx_files:
        logger.info(f"  Parsing {pwx_file.name}...")

        trackpoints = parser.parse_file(str(pwx_file))
        if trackpoints is None:
            errors.append(pwx_file.name)
            logger.error(f"    failed (no power data)")
            continue

        metrics = parser.calculate_metrics(trackpoints)
        if metrics is None:
            errors.append(pwx_file.name)
            logger.error(f"    failed (calc error)")
            continue

        # Add filename and date
        metrics['filename'] = pwx_file.name
        metrics['file_stem'] = pwx_file.stem

        # Try to extract date from filename (assuming ISO format: YYYY-MM-DD_...)
        try:
            metrics['date'] = pwx_file.stem.split('_')[0]
        except:
            metrics['date'] = None

        results.append(metrics)
        logger.info(f"    done - NP: {metrics['np']}W, VI: {metrics['vi']}, TSS: {metrics['tss']}")

    # Write main CSV
    if results:
        output_csv = output_folder / 'workouts_analysis.csv'
        with open(output_csv, 'w', newline='') as f:
            fieldnames = sorted(results[0].keys())
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(results)

        logger.info(f"\n>>> Success! {len(results)} workouts analyzed")
        logger.info(f"    Output: {output_csv}")

        # Generate summary stats
        generate_summary_stats(results, output_folder, config)

    if errors:
        logger.warning(f"\n>>> {len(errors)} files failed to process")
        for err in errors:
            logger.warning(f"    - {err}")

    return results


def generate_summary_stats(results, output_folder, config):
    """Generate summary statistics"""

    # Calculate aggregate stats
    vis = [r['vi'] for r in results if r['vi'] is not None]
    avg_vi = mean(vis) if vis else None
    avg_if = mean([r['if'] for r in results])
    avg_tss = mean([r['tss'] for r in results])
    total_hours = sum([r['duration_minutes'] for r in results]) / 60
    total_tss = sum([r['tss'] for r in results])

    # Count workout types by IF
    z2_endurance = sum(1 for r in results if r['if'] < 0.75 and (r['vi'] is None or r['vi'] < 1.10))
    threshold = sum(1 for r in results if 0.88 <= r['if'] <= 1.05)
    vo2max = sum(1 for r in results if 1.06 <= r['if'] <= 1.20)
    recovery = sum(1 for r in results if r['if'] < 0.55)

    # Decoupling stats
    decouplings = [r['decoupling_pct'] for r in results if r['decoupling_pct'] is not None]
    avg_decoupling = mean(decouplings) if decouplings else None

    summary = {
        'total_files': len(results),
        'total_hours': round(total_hours, 1),
        'total_tss': round(total_tss, 0),
        'avg_vi': round(avg_vi, 3) if avg_vi else None,
        'avg_if': round(avg_if, 3),
        'avg_tss_per_workout': round(avg_tss, 0),
        'avg_decoupling_pct': round(avg_decoupling, 1) if avg_decoupling else None,
        'z2_endurance_count': z2_endurance,
        'threshold_count': threshold,
        'vo2max_count': vo2max,
        'recovery_count': recovery,
        'config_ftp': config.get('athlete', {}).get('ftp', 250),
        'config_lthr': config.get('athlete', {}).get('lthr', 170),
    }

    # Write summary
    summary_file = output_folder / 'summary_stats.json'
    with open(summary_file, 'w') as f:
        json.dump(summary, f, indent=2)

    logger.info(f"\nSummary Statistics:")
    logger.info(f"  Total workouts: {summary['total_files']}")
    logger.info(f"  Total hours: {summary['total_hours']}")
    logger.info(f"  Total TSS: {summary['total_tss']}")
    logger.info(f"  Avg VI: {summary['avg_vi']} (lower = better pacing)")
    logger.info(f"  Avg IF: {summary['avg_if']}")
    logger.info(f"  Avg Decoupling: {summary['avg_decoupling_pct']}%")
    logger.info(f"  Workouts by type:")
    logger.info(f"    - Z2 Endurance: {summary['z2_endurance_count']}")
    logger.info(f"    - Threshold: {summary['threshold_count']}")
    logger.info(f"    - VO2max: {summary['vo2max_count']}")
    logger.info(f"    - Recovery: {summary['recovery_count']}")


def main():
    """Main entry point"""
    import argparse

    parser = argparse.ArgumentParser(description='Gravel God PWX Parser')
    parser.add_argument('--pwx-folder', default='./pwx_files', help='Folder containing PWX files')
    parser.add_argument('--output-folder', default='./output', help='Output folder for results')
    parser.add_argument('--config', default='config.json', help='Config file path')

    args = parser.parse_args()

    process_pwx_folder(args.pwx_folder, args.output_folder, args.config)


if __name__ == '__main__':
    main()
