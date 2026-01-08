#!/usr/bin/env python3
"""
Gravel God Coaching Analysis Engine
Generates coaching recommendations based on training metrics
"""

import json
import csv
from datetime import datetime
from pathlib import Path
from statistics import mean, stdev


class GravelGodAnalyzer:
    """Core coaching analysis logic"""

    def __init__(self, config, results):
        self.config = config
        self.results = sorted(results, key=lambda x: x.get('filename', ''))
        self.athlete = config.get('athlete', {})
        self.analysis_config = config.get('analysis', {})

    def generate_reports(self, output_folder):
        """Generate all analysis reports"""
        output_folder = Path(output_folder)
        output_folder.mkdir(exist_ok=True)

        # Workout analysis CSV
        self._write_workout_csv(output_folder)

        # Weekly summary
        self._write_weekly_summary(output_folder)

        # Coaching alerts
        self._write_alerts(output_folder)

        # Trends
        self._write_trends(output_folder)

        # Coaching recommendations
        self._write_recommendations(output_folder)

    def _write_workout_csv(self, output_folder):
        """Write detailed workout analysis"""
        output_file = output_folder / 'workouts.csv'

        with open(output_file, 'w', newline='') as f:
            if self.results:
                fieldnames = sorted(self.results[0].keys())
                writer = csv.DictWriter(f, fieldnames=fieldnames)
                writer.writeheader()
                writer.writerows(self.results)

    def _write_weekly_summary(self, output_folder):
        """Generate weekly training summaries"""

        # Group by week (using date if available)
        weeks = {}
        for result in self.results:
            date = result.get('date', 'unknown')
            week_key = date[:7] if date and date != 'unknown' else 'unknown'

            if week_key not in weeks:
                weeks[week_key] = []
            weeks[week_key].append(result)

        # Calculate weekly stats
        weekly_stats = []
        for week, workouts in sorted(weeks.items()):
            vis = [w['vi'] for w in workouts if w['vi']]
            decouplings = [w['decoupling_pct'] for w in workouts if w['decoupling_pct']]

            stats = {
                'week': week,
                'workouts': len(workouts),
                'total_hours': round(sum(w['duration_minutes'] for w in workouts) / 60, 1),
                'total_tss': round(sum(w['tss'] for w in workouts), 0),
                'avg_vi': round(mean(vis), 3) if vis else None,
                'avg_if': round(mean([w['if'] for w in workouts]), 3),
                'avg_decoupling': round(mean(decouplings), 1) if decouplings else None,
            }
            weekly_stats.append(stats)

        # Write CSV
        if weekly_stats:
            output_file = output_folder / 'weekly_summary.csv'
            with open(output_file, 'w', newline='') as f:
                writer = csv.DictWriter(f, fieldnames=weekly_stats[0].keys())
                writer.writeheader()
                writer.writerows(weekly_stats)

    def _write_alerts(self, output_folder):
        """Generate coaching alerts"""

        alerts = []

        # Alert thresholds
        vi_threshold = self.analysis_config.get('vi_threshold_acceptable', 1.10)
        vi_warning = 1.15
        decoupling_threshold = self.analysis_config.get('decoupling_threshold_warning', 10.0)

        for result in self.results:
            workout_alerts = []

            # VI alert
            if result['vi'] and result['vi'] > vi_threshold:
                severity = 'yellow' if result['vi'] < vi_warning else 'red'
                workout_alerts.append({
                    'type': 'PACING_ISSUE',
                    'severity': severity,
                    'message': f"VI {result['vi']:.2f} - pacing was inconsistent. Target <1.05 for steady rides."
                })

            # Decoupling alert
            if result['decoupling_pct'] and result['decoupling_pct'] > decoupling_threshold:
                workout_alerts.append({
                    'type': 'AEROBIC_FATIGUE',
                    'severity': 'orange',
                    'message': f"Decoupling {result['decoupling_pct']:.1f}% - aerobic system fatigued or underdeveloped. Target <5%."
                })

            # High TSS alert
            if result['tss'] > 200:
                workout_alerts.append({
                    'type': 'HIGH_LOAD',
                    'severity': 'info',
                    'message': f"TSS {result['tss']:.0f} - significant training load. Ensure adequate recovery."
                })

            # Very high IF (overreaching on steady ride)
            if result['if'] > 0.85 and result['duration_minutes'] > 90:
                workout_alerts.append({
                    'type': 'HIGH_INTENSITY_LONG_RIDE',
                    'severity': 'yellow',
                    'message': f"IF {result['if']:.2f} for {result['duration_minutes']:.0f}min - this was hard! Watch recovery."
                })

            if workout_alerts:
                alerts.append({
                    'filename': result['filename'],
                    'date': result.get('date'),
                    'alerts': workout_alerts
                })

        # Write alerts
        output_file = output_folder / 'alerts.json'
        with open(output_file, 'w') as f:
            json.dump(alerts, f, indent=2)

        # Also write alert summary
        alert_summary = {
            'total_workouts': len(self.results),
            'workouts_with_alerts': len(alerts),
            'pacing_issues': sum(1 for a in alerts for alert in a['alerts'] if alert['type'] == 'PACING_ISSUE'),
            'aerobic_fatigue_issues': sum(1 for a in alerts for alert in a['alerts'] if alert['type'] == 'AEROBIC_FATIGUE'),
            'high_load_workouts': sum(1 for a in alerts for alert in a['alerts'] if alert['type'] == 'HIGH_LOAD'),
        }
        summary_file = output_folder / 'alert_summary.json'
        with open(summary_file, 'w') as f:
            json.dump(alert_summary, f, indent=2)

    def _write_trends(self, output_folder):
        """Analyze training trends"""

        if len(self.results) < 2:
            trends = {'error': 'Need at least 2 workouts for trend analysis'}
            output_file = output_folder / 'trends.json'
            with open(output_file, 'w') as f:
                json.dump(trends, f, indent=2)
            return

        # VI trend (is pacing improving or degrading?)
        vis = [r['vi'] for r in self.results if r['vi']]
        if len(vis) >= 2:
            first_half_vi = mean(vis[:len(vis)//2])
            second_half_vi = mean(vis[len(vis)//2:])
            vi_trend = 'improving' if second_half_vi < first_half_vi else 'degrading'
            vi_change = ((second_half_vi - first_half_vi) / first_half_vi) * 100
        else:
            vi_trend = 'insufficient_data'
            vi_change = None
            first_half_vi = None
            second_half_vi = None

        # Decoupling trend
        decouplings = [r['decoupling_pct'] for r in self.results if r['decoupling_pct']]
        if len(decouplings) >= 2:
            first_half_dec = mean(decouplings[:len(decouplings)//2])
            second_half_dec = mean(decouplings[len(decouplings)//2:])
            decoupling_trend = 'improving' if second_half_dec < first_half_dec else 'degrading'
        else:
            decoupling_trend = 'insufficient_data'
            first_half_dec = None
            second_half_dec = None

        # IF trend (training intensity)
        ifs = [r['if'] for r in self.results]
        first_half_if = mean(ifs[:len(ifs)//2])
        second_half_if = mean(ifs[len(ifs)//2:])
        if_trend = 'increasing' if second_half_if > first_half_if else 'decreasing'

        # TSS trend (training load)
        tss_values = [r['tss'] for r in self.results]
        first_half_tss = mean(tss_values[:len(tss_values)//2])
        second_half_tss = mean(tss_values[len(tss_values)//2:])
        tss_trend = 'increasing' if second_half_tss > first_half_tss else 'decreasing'

        trends = {
            'vi_trend': vi_trend,
            'vi_first_half_avg': round(first_half_vi, 3) if first_half_vi else None,
            'vi_second_half_avg': round(second_half_vi, 3) if second_half_vi else None,
            'vi_change_pct': round(vi_change, 1) if vi_change else None,
            'decoupling_trend': decoupling_trend,
            'decoupling_first_half_avg': round(first_half_dec, 1) if first_half_dec else None,
            'decoupling_second_half_avg': round(second_half_dec, 1) if second_half_dec else None,
            'if_trend': if_trend,
            'if_first_half_avg': round(first_half_if, 3),
            'if_second_half_avg': round(second_half_if, 3),
            'tss_trend': tss_trend,
            'tss_first_half_avg': round(first_half_tss, 0),
            'tss_second_half_avg': round(second_half_tss, 0),
            'power_stability': 'stable' if mean([r['vi'] for r in self.results if r['vi']]) < 1.10 else 'variable',
        }

        output_file = output_folder / 'trends.json'
        with open(output_file, 'w') as f:
            json.dump(trends, f, indent=2)

    def _write_recommendations(self, output_folder):
        """Generate coaching recommendations based on analysis"""

        recommendations = []

        # Overall stats
        vis = [r['vi'] for r in self.results if r['vi']]
        decouplings = [r['decoupling_pct'] for r in self.results if r['decoupling_pct']]
        ifs = [r['if'] for r in self.results]

        avg_vi = mean(vis) if vis else None
        avg_decoupling = mean(decouplings) if decouplings else None
        avg_if = mean(ifs)

        # Pacing recommendations
        if avg_vi and avg_vi > 1.10:
            recommendations.append({
                'category': 'PACING',
                'priority': 'high',
                'observation': f"Average VI is {avg_vi:.2f} - workouts are inconsistently paced",
                'recommendation': "Focus on steady-state efforts. Use power targets and avoid surging. For Z2 rides, stay within 5W of target.",
                'drill': "Do 3x20min at exactly 65-70% FTP with goal of VI < 1.03"
            })
        elif avg_vi and avg_vi > 1.05:
            recommendations.append({
                'category': 'PACING',
                'priority': 'medium',
                'observation': f"Average VI is {avg_vi:.2f} - pacing could be more consistent",
                'recommendation': "Good pacing overall, but room for improvement on endurance rides.",
                'drill': "Practice 60min steady rides with VI target < 1.03"
            })

        # Aerobic efficiency recommendations
        if avg_decoupling and avg_decoupling > 10:
            recommendations.append({
                'category': 'AEROBIC_BASE',
                'priority': 'high',
                'observation': f"Average decoupling is {avg_decoupling:.1f}% - aerobic system needs work",
                'recommendation': "Increase Z2 volume. Heart rate is drifting significantly, indicating aerobic ceiling is being hit.",
                'drill': "Add 1-2 hours of Z2 per week. Monitor decoupling - target <5% for rides under 3 hours."
            })
        elif avg_decoupling and avg_decoupling > 5:
            recommendations.append({
                'category': 'AEROBIC_BASE',
                'priority': 'medium',
                'observation': f"Average decoupling is {avg_decoupling:.1f}% - room for aerobic improvement",
                'recommendation': "Aerobic base is developing. Continue Z2 work.",
                'drill': "Maintain current Z2 volume. Track decoupling trend over 4-6 weeks."
            })

        # Intensity distribution
        z2_workouts = sum(1 for r in self.results if r['if'] < 0.75)
        hard_workouts = sum(1 for r in self.results if r['if'] > 0.85)
        total = len(self.results)

        if total > 0:
            z2_pct = z2_workouts / total * 100
            hard_pct = hard_workouts / total * 100

            if z2_pct < 70:
                recommendations.append({
                    'category': 'POLARIZATION',
                    'priority': 'high',
                    'observation': f"Only {z2_pct:.0f}% of workouts are Z2 (target 80%)",
                    'recommendation': "Too much time in 'gray zone'. Either go easy (Z2) or go hard (threshold+), but avoid moderate intensity.",
                    'drill': "Next 4 weeks: 80% Z2, 20% hard. No moderate rides."
                })

            if hard_pct > 25:
                recommendations.append({
                    'category': 'RECOVERY',
                    'priority': 'medium',
                    'observation': f"{hard_pct:.0f}% of workouts are high intensity",
                    'recommendation': "High intensity ratio. Ensure adequate recovery between hard sessions.",
                    'drill': "Never do hard workouts on consecutive days. Add recovery day after any TSS >100 session."
                })

        # Summary
        summary = {
            'athlete': self.athlete.get('name', 'Athlete'),
            'workouts_analyzed': len(self.results),
            'avg_vi': round(avg_vi, 3) if avg_vi else None,
            'avg_decoupling': round(avg_decoupling, 1) if avg_decoupling else None,
            'avg_if': round(avg_if, 3),
            'recommendations': recommendations,
            'top_priority': recommendations[0] if recommendations else None
        }

        output_file = output_folder / 'recommendations.json'
        with open(output_file, 'w') as f:
            json.dump(summary, f, indent=2)

        # Also write human-readable report
        self._write_coaching_report(output_folder, summary)

    def _write_coaching_report(self, output_folder, summary):
        """Write human-readable coaching report"""

        report_lines = [
            f"# Gravel God Coaching Report",
            f"## Athlete: {summary['athlete']}",
            f"## Workouts Analyzed: {summary['workouts_analyzed']}",
            "",
            "---",
            "",
            "## Key Metrics",
            f"- **Average VI:** {summary['avg_vi']} (target: <1.05)",
            f"- **Average Decoupling:** {summary['avg_decoupling']}% (target: <5%)",
            f"- **Average IF:** {summary['avg_if']}",
            "",
            "---",
            "",
            "## Recommendations",
            "",
        ]

        for i, rec in enumerate(summary['recommendations'], 1):
            report_lines.extend([
                f"### {i}. {rec['category']} ({rec['priority'].upper()} priority)",
                f"**Observation:** {rec['observation']}",
                "",
                f"**Recommendation:** {rec['recommendation']}",
                "",
                f"**Drill:** {rec['drill']}",
                "",
                "---",
                "",
            ])

        if not summary['recommendations']:
            report_lines.append("No specific recommendations. Training metrics look solid!")

        output_file = output_folder / 'coaching_report.md'
        with open(output_file, 'w') as f:
            f.write('\n'.join(report_lines))
