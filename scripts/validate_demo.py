#!/usr/bin/env python3
"""Reproducible count audit; not a claim of universal boundary accuracy."""
import argparse
import json
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from lomokino.engine import load_document, export_sequence, export_video, natural_key

EXPECTED = {'1.jpg': 4, '2.jpg': 4, '3.jpg': 4, '4.jpg': 4, '5.jpg': 4,
            '6.jpg': 4, '7.jpg': 3, '8.jpg': 9, 'old.jpg': 8}

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--demo', type=Path, default=Path(__file__).resolve().parents[1] / 'demo')
    parser.add_argument('--output', type=Path, default=Path('output/demo-audit'))
    parser.add_argument('--export', action='store_true')
    args = parser.parse_args()
    documents, rows = [], []
    available = [(args.demo / name, EXPECTED[name], 'original scan') for name in sorted(EXPECTED, key=natural_key) if (args.demo / name).is_file()]
    public = Path(__file__).resolve().parents[1] / 'assets/demo/synthetic_long_scan.png'
    if public.is_file(): available.append((public, 8, 'AI-generated synthetic scan'))
    for source, expected_count, kind in available:
        name = source.name
        doc, result = load_document(source)
        documents.append(doc)
        rows.append({'source': name, 'expected_count': expected_count, 'kind': kind, 'detected_count': len(doc.regions),
                     'count_matches': len(doc.regions) == expected_count,
                     'content_x': list(result.content_bounds), 'rects': [r.to_dict()['rect'] for r in doc.regions]})
    args.output.mkdir(parents=True, exist_ok=True)
    report = {'method': 'Manually reviewed frame counts on available original and synthetic scans; no pixel-boundary ground truth.',
              'missing_original_fixtures': [name for name in EXPECTED if not (args.demo / name).is_file()],
              'files': rows, 'frames': sum(len(d.regions) for d in documents)}
    (args.output / 'report.json').write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
    if args.export:
        order = [r.id for d in documents for r in d.regions]
        export_sequence(documents, order, args.output / 'frames')
        export_video(documents, order, args.output / 'demo.mp4', {'fps': 12, 'width': 1080, 'height': 400})
    print(json.dumps({'files_matching_counts': sum(r['count_matches'] for r in rows), 'files': len(rows), 'frames': report['frames']}))
    return 0 if rows and all(r['count_matches'] for r in rows) else 1

if __name__ == '__main__': sys.exit(main())
