// Simplified Gen 9 damage calculator
// Returns { min, max, minPct, maxPct, koChance, effectiveness }

window.calcDamage = function(attacker, defender, move, field, opts = {}) {
  if (!attacker || !defender || !move) return null;
  if (move.category === "Status" || move.power === 0) return null;

  const TYPE_CHART = window.TYPE_CHART;
  const stages = opts.attackerStages || { atk: 0, def: 0, spa: 0, spd: 0, spe: 0 };
  const defStages = opts.defenderStages || { atk: 0, def: 0, spa: 0, spd: 0, spe: 0 };

  const stageMul = (s) => s >= 0 ? (2 + s) / 2 : 2 / (2 - s);

  // Effective stats
  const isPhys = move.category === "Physical";
  const atkStat = isPhys ? attacker.stats.atk * stageMul(stages.atk) : attacker.stats.spa * stageMul(stages.spa);
  const defStat = isPhys ? defender.stats.def * stageMul(defStages.def) : defender.stats.spd * stageMul(defStages.spd);

  // STAB
  const attackerTypes = opts.attackerTeraActive ? [opts.attackerTeraType] : attacker.types;
  let stab = attackerTypes.includes(move.type) ? 1.5 : 1;
  if (opts.attackerTeraActive && attacker.types.includes(move.type) && opts.attackerTeraType === move.type) stab = 2;

  // Effectiveness
  const defTypes = opts.defenderTeraActive ? [opts.defenderTeraType] : defender.types;
  let effectiveness = 1;
  defTypes.forEach(t => {
    const row = TYPE_CHART[t];
    if (row && row[move.type] !== undefined) effectiveness *= row[move.type];
  });

  // Field modifiers
  let fieldMul = 1;
  if (field.weather === "sun" && move.type === "Fire") fieldMul *= 1.5;
  if (field.weather === "sun" && move.type === "Water") fieldMul *= 0.5;
  if (field.weather === "rain" && move.type === "Water") fieldMul *= 1.5;
  if (field.weather === "rain" && move.type === "Fire") fieldMul *= 0.5;
  if (field.terrain === "electric" && move.type === "Electric" && !opts.defenderAirborne) fieldMul *= 1.3;
  if (field.terrain === "grassy" && move.type === "Grass" && !opts.attackerAirborne) fieldMul *= 1.3;
  if (field.terrain === "psychic" && move.type === "Psychic" && !opts.attackerAirborne) fieldMul *= 1.3;
  if (field.terrain === "misty" && move.type === "Dragon" && !opts.defenderAirborne) fieldMul *= 0.5;

  // Spread move
  if (move.target === "all-foes") fieldMul *= 0.75;

  // Screens (simplified)
  if (!opts.crit) {
    if (isPhys && field.defenderReflect) fieldMul *= 0.5;
    if (!isPhys && field.defenderLightScreen) fieldMul *= 0.5;
  }

  // Item
  let itemMul = 1;
  if (attacker.item === "Life Orb") itemMul *= 1.3;
  if (attacker.item === "Choice Specs" && !isPhys) itemMul *= 1.5;
  if (attacker.item === "Choice Band" && isPhys) itemMul *= 1.5;
  if (attacker.item === "Mystic Water" && move.type === "Water") itemMul *= 1.2;

  // Burn
  if (isPhys && opts.attackerBurned && attacker.ability !== "Guts") fieldMul *= 0.5;

  // Base damage formula
  const level = attacker.level || 50;
  const base = Math.floor(Math.floor((Math.floor(2 * level / 5) + 2) * move.power * atkStat / defStat) / 50) + 2;

  const withMods = base * stab * effectiveness * fieldMul * itemMul;

  // Random factor 0.85 - 1.00
  const min = Math.floor(withMods * 0.85);
  const max = Math.floor(withMods * 1.00);

  const hpMax = defender.stats.hp;
  const currentHp = opts.defenderHp ?? hpMax;

  return {
    min,
    max,
    minPct: Math.round((min / hpMax) * 1000) / 10,
    maxPct: Math.round((max / hpMax) * 1000) / 10,
    effectiveness,
    koChance: max >= currentHp ? (min >= currentHp ? "Guaranteed OHKO" : `Possible KO (${Math.round((max - currentHp + 1) / (max - min + 1) * 100)}%)`) : "No KO"
  };
};
