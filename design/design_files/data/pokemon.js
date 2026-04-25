// Sample Reg G-style matchup data
// Keys: name, types, ability, item, nature, level, evs, ivs, baseStats, moves, tera
// Stats are precomputed for level 50 with given EVs/IVs/nature

window.POKEMON_DATA = {
  // ALLY 1: Calyrex-Shadow Rider
  calyrexShadow: {
    id: "calyrexShadow",
    name: "Calyrex-Shadow",
    types: ["Psychic", "Ghost"],
    ability: "As One (Spectrier)",
    item: "Life Orb",
    nature: "Timid",
    teraType: "Normal",
    level: 50,
    gender: "—",
    baseStats: { hp: 100, atk: 85, def: 80, spa: 165, spd: 100, spe: 150 },
    evs:       { hp: 4,   atk: 0,  def: 0,  spa: 252, spd: 0,   spe: 252 },
    ivs:       { hp: 31,  atk: 0,  def: 31, spa: 31,  spd: 31,  spe: 31 },
    stats:     { hp: 175, atk: 95, def: 110, spa: 217, spd: 130, spe: 200 },
    moves: [
      { name: "Astral Barrage", type: "Ghost", category: "Special", power: 120, acc: 100, pp: 8, target: "all-foes", desc: "Spread move, hits both opponents at 0.75x" },
      { name: "Psyshock", type: "Psychic", category: "Special", power: 80, acc: 100, pp: 16, target: "single", desc: "Damages with physical defense" },
      { name: "Nasty Plot", type: "Dark", category: "Status", power: 0, acc: 100, pp: 32, target: "self", desc: "+2 Special Attack" },
      { name: "Protect", type: "Normal", category: "Status", power: 0, acc: 100, pp: 16, target: "self", desc: "Blocks moves this turn" }
    ]
  },
  // ALLY 2: Urshifu-Rapid Strike
  urshifuRapid: {
    id: "urshifuRapid",
    name: "Urshifu-Rapid Strike",
    types: ["Fighting", "Water"],
    ability: "Unseen Fist",
    item: "Mystic Water",
    nature: "Jolly",
    teraType: "Water",
    level: 50,
    gender: "♂",
    baseStats: { hp: 100, atk: 130, def: 100, spa: 63, spd: 60, spe: 97 },
    evs:       { hp: 4,   atk: 252, def: 0,   spa: 0,  spd: 0,  spe: 252 },
    ivs:       { hp: 31,  atk: 31,  def: 31,  spa: 0,  spd: 31, spe: 31 },
    stats:     { hp: 175, atk: 189, def: 120, spa: 67, spd: 80, spe: 156 },
    moves: [
      { name: "Surging Strikes", type: "Water", category: "Physical", power: 25, acc: 100, pp: 8, target: "single", desc: "3 hits, always crits, ignores Protect" },
      { name: "Close Combat", type: "Fighting", category: "Physical", power: 120, acc: 100, pp: 8, target: "single", desc: "Lowers user's Def/SpD" },
      { name: "Aqua Jet", type: "Water", category: "Physical", power: 40, acc: 100, pp: 32, target: "single", desc: "+1 priority" },
      { name: "Detect", type: "Fighting", category: "Status", power: 0, acc: 100, pp: 8, target: "self", desc: "Blocks moves this turn" }
    ]
  },
  // OPPONENT 1: Miraidon
  miraidon: {
    id: "miraidon",
    name: "Miraidon",
    types: ["Electric", "Dragon"],
    ability: "Hadron Engine",
    item: "Choice Specs",
    nature: "Modest",
    teraType: "Electric",
    level: 50,
    gender: "—",
    baseStats: { hp: 100, atk: 85, def: 100, spa: 135, spd: 115, spe: 135 },
    evs:       { hp: 4,   atk: 0,  def: 0,   spa: 252, spd: 0,   spe: 252 },
    ivs:       { hp: 31,  atk: 31, def: 31,  spa: 31,  spd: 31,  spe: 31 },
    stats:     { hp: 175, atk: 105, def: 130, spa: 205, spd: 145, spe: 187 },
    moves: [
      { name: "Electro Drift", type: "Electric", category: "Special", power: 100, acc: 100, pp: 8, target: "single", desc: "1.33x if super-effective" },
      { name: "Draco Meteor", type: "Dragon", category: "Special", power: 130, acc: 90, pp: 8, target: "single", desc: "Lowers SpA by 2" },
      { name: "Volt Switch", type: "Electric", category: "Special", power: 70, acc: 100, pp: 32, target: "single", desc: "Switches out after damage" },
      { name: "Dazzling Gleam", type: "Fairy", category: "Special", power: 80, acc: 100, pp: 16, target: "all-foes", desc: "Spread move, 0.75x" }
    ]
  },
  // OPPONENT 2: Farigiraf
  farigiraf: {
    id: "farigiraf",
    name: "Farigiraf",
    types: ["Normal", "Psychic"],
    ability: "Armor Tail",
    item: "Electric Seed",
    nature: "Sassy",
    teraType: "Fairy",
    level: 50,
    gender: "♀",
    baseStats: { hp: 120, atk: 90, def: 70, spa: 110, spd: 70, spe: 60 },
    evs:       { hp: 252, atk: 0,  def: 4,   spa: 0,   spd: 252, spe: 0 },
    ivs:       { hp: 31,  atk: 0,  def: 31,  spa: 31,  spd: 31,  spe: 0 },
    stats:     { hp: 215, atk: 100, def: 96, spa: 135, spd: 156, spe: 76 },
    moves: [
      { name: "Trick Room", type: "Psychic", category: "Status", power: 0, acc: 100, pp: 8, target: "field", desc: "Reverses speed for 5 turns" },
      { name: "Helping Hand", type: "Normal", category: "Status", power: 0, acc: 100, pp: 32, target: "ally", desc: "1.5x ally damage" },
      { name: "Foul Play", type: "Dark", category: "Physical", power: 95, acc: 100, pp: 24, target: "single", desc: "Uses target's Atk stat" },
      { name: "Psychic Noise", type: "Psychic", category: "Special", power: 75, acc: 100, pp: 16, target: "single", desc: "Blocks healing for 2 turns" }
    ]
  }
};

// Type effectiveness chart (defender type -> attacker type -> multiplier)
window.TYPE_CHART = {
  Normal:   { Fighting: 2, Ghost: 0 },
  Fire:     { Water: 2, Ground: 2, Rock: 2, Fire: 0.5, Grass: 0.5, Ice: 0.5, Bug: 0.5, Steel: 0.5, Fairy: 0.5 },
  Water:    { Electric: 2, Grass: 2, Fire: 0.5, Water: 0.5, Ice: 0.5, Steel: 0.5 },
  Electric: { Ground: 2, Electric: 0.5, Flying: 0.5, Steel: 0.5 },
  Grass:    { Fire: 2, Ice: 2, Poison: 2, Flying: 2, Bug: 2, Water: 0.5, Electric: 0.5, Grass: 0.5, Ground: 0.5 },
  Ice:      { Fire: 2, Fighting: 2, Rock: 2, Steel: 2, Ice: 0.5 },
  Fighting: { Flying: 2, Psychic: 2, Fairy: 2, Bug: 0.5, Rock: 0.5, Dark: 0.5 },
  Poison:   { Ground: 2, Psychic: 2, Grass: 0.5, Fighting: 0.5, Poison: 0.5, Bug: 0.5, Fairy: 0.5 },
  Ground:   { Water: 2, Grass: 2, Ice: 2, Poison: 0.5, Rock: 0.5, Electric: 0 },
  Flying:   { Electric: 2, Ice: 2, Rock: 2, Grass: 0.5, Fighting: 0.5, Bug: 0.5, Ground: 0 },
  Psychic:  { Bug: 2, Ghost: 2, Dark: 2, Fighting: 0.5, Psychic: 0.5 },
  Bug:      { Fire: 2, Flying: 2, Rock: 2, Grass: 0.5, Fighting: 0.5, Ground: 0.5 },
  Rock:     { Water: 2, Grass: 2, Fighting: 2, Ground: 2, Steel: 2, Normal: 0.5, Fire: 0.5, Poison: 0.5, Flying: 0.5 },
  Ghost:    { Ghost: 2, Dark: 2, Poison: 0.5, Bug: 0.5, Normal: 0, Fighting: 0 },
  Dragon:   { Ice: 2, Dragon: 2, Fairy: 2, Fire: 0.5, Water: 0.5, Electric: 0.5, Grass: 0.5 },
  Dark:     { Fighting: 2, Bug: 2, Fairy: 2, Ghost: 0.5, Dark: 0.5, Psychic: 0 },
  Steel:    { Fire: 2, Fighting: 2, Ground: 2, Normal: 0.5, Grass: 0.5, Ice: 0.5, Flying: 0.5, Psychic: 0.5, Bug: 0.5, Rock: 0.5, Dragon: 0.5, Steel: 0.5, Fairy: 0.5, Poison: 0 },
  Fairy:    { Poison: 2, Steel: 2, Fighting: 0.5, Bug: 0.5, Dark: 0.5, Dragon: 0 }
};

// Type colors — muted analytical palette, original design
window.TYPE_COLORS = {
  Normal:   "#a8a878",
  Fire:     "#e08a4d",
  Water:    "#5a8fd6",
  Electric: "#d4b73c",
  Grass:    "#6cb86c",
  Ice:      "#8ec9d4",
  Fighting: "#c44b4b",
  Poison:   "#a55cb0",
  Ground:   "#c9a96e",
  Flying:   "#9aaad6",
  Psychic:  "#e06b8e",
  Bug:      "#a8b850",
  Rock:     "#a89868",
  Ghost:    "#7060a0",
  Dragon:   "#6a4ad6",
  Dark:     "#605850",
  Steel:    "#9098a8",
  Fairy:    "#d68fb8"
};
