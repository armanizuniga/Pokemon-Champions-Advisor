// Example battle state matching data/battle_states/example.json
// Garchomp + Incineroar vs Torkoal + Venusaur with Sun active

export const INITIAL_ALLIES = [
  {
    id: "garchomp",
    name: "Garchomp",
    types: ["Dragon", "Ground"],
    ability: "Rough Skin",
    item: "Garchompite",
    nature: "Jolly",
    level: 50,
    baseStats: { hp: 108, atk: 130, def: 95, spa: 80, spd: 85, spe: 102 },
    evs:       { hp: 4,   atk: 252, def: 0,  spa: 0,  spd: 0,  spe: 252 },
    stats:     { hp: 168, atk: 166, def: 100, spa: 76, spd: 90, spe: 151 },
    moves: [
      { name: "Earthquake",  type: "Ground",  category: "Physical", power: 100, acc: 100, pp: 16 },
      { name: "Rock Slide",  type: "Rock",    category: "Physical", power: 75,  acc: 90,  pp: 16 },
      { name: "Icy Wind",    type: "Ice",     category: "Special",  power: 55,  acc: 95,  pp: 24 },
      { name: "Protect",     type: "Normal",  category: "Status",   power: 0,   acc: 100, pp: 16 },
    ],
  },
  {
    id: "incineroar",
    name: "Incineroar",
    types: ["Fire", "Dark"],
    ability: "Intimidate",
    item: "Sitrus Berry",
    nature: "Careful",
    level: 50,
    baseStats: { hp: 95, atk: 115, def: 90, spa: 80, spd: 90, spe: 60 },
    evs:       { hp: 252, atk: 4, def: 0,   spa: 0,  spd: 252, spe: 0 },
    stats:     { hp: 167, atk: 116, def: 105, spa: 90, spd: 120, spe: 65 },
    moves: [
      { name: "Fake Out",      type: "Normal", category: "Physical", power: 40,  acc: 100, pp: 16 },
      { name: "Flare Blitz",   type: "Fire",   category: "Physical", power: 120, acc: 100, pp: 8  },
      { name: "Parting Shot",  type: "Dark",   category: "Status",   power: 0,   acc: 100, pp: 32 },
      { name: "Protect",       type: "Normal", category: "Status",   power: 0,   acc: 100, pp: 16 },
    ],
  },
];

export const INITIAL_OPPONENTS = [
  {
    id: "torkoal",
    name: "Torkoal",
    types: ["Fire"],
    ability: "Drought",
    item: null,
    nature: "Modest",
    level: 50,
    baseStats: { hp: 70, atk: 85, def: 140, spa: 85, spd: 70, spe: 20 },
    evs:       { hp: 252, atk: 0, def: 0, spa: 252, spd: 4, spe: 0 },
    stats:     { hp: 155, atk: 92, def: 155, spa: 140, spd: 82, spe: 25 },
    moves: [],
  },
  {
    id: "venusaur",
    name: "Venusaur",
    types: ["Grass", "Poison"],
    ability: "Chlorophyll",
    item: null,
    nature: "Modest",
    level: 50,
    baseStats: { hp: 80, atk: 82, def: 83, spa: 100, spd: 100, spe: 80 },
    evs:       { hp: 4, atk: 0, def: 0, spa: 252, spd: 0, spe: 252 },
    stats:     { hp: 155, atk: 87, def: 98, spa: 145, spd: 115, spe: 130 },
    moves: [],
  },
];

export const INITIAL_ALLY_TEAM = [
  "Garchomp", "Incineroar", "Arcanine", "Rillaboom",
];

export const INITIAL_OPP_TEAM = [
  "Torkoal", "Venusaur", "Grimmsnarl", "Tyranitar",
];

export const INITIAL_BACK = {
  ally: [
    { id: "arcanine",  name: "Arcanine",  hpPercent: 1.0 },
    { id: "rillaboom", name: "Rillaboom", hpPercent: 1.0 },
  ],
  opp: [
    { id: "grimmsnarl", name: "Grimmsnarl", hpPercent: 1.0 },
    { id: "tyranitar",  name: "Tyranitar",  hpPercent: 1.0 },
  ],
};

export function makeMonState(mon) {
  return {
    hp:        mon.stats.hp,
    status:    "none",
    stages:    { atk: 0, def: 0, spa: 0, spd: 0, spe: 0 },
    volatiles: [],
  };
}
