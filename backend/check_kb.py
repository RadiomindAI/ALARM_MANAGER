import json
with open('data/alarm_kb.json', encoding='utf-8') as f:
    kb = json.load(f)
profiles = kb['alarm_profiles']
sorted_p = sorted(profiles.items(), key=lambda x: x[1]['filterability_score'], reverse=True)
print('TOP 15 ALLARMI PER SCORE:')
for name, p in sorted_p[:15]:
    score = p['filterability_score']
    me    = p['affected_me_count']
    occ   = p['total_occurrences']
    print(f'  score={score:.4f} me={me:>4} occ={occ:>9,} | {name[:70]}')
print()
print('Distribuzione score:')
scores = [p['filterability_score'] for p in profiles.values()]
for t in [0.9, 0.85, 0.8, 0.7, 0.6, 0.5]:
    count = sum(1 for s in scores if s >= t)
    print(f'  >= {t}: {count} allarmi')
