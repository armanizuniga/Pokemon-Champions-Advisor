const { calculate, Pokemon, Move, Field, Generations } = require("@smogon/calc");

const gen = Generations.get(9);

function buildField(fieldData) {
  return new Field({
    weather: fieldData.weather ?? undefined,
    terrain: fieldData.terrain ?? undefined,
    isTrickRoom: fieldData.trick_room ?? false,
    attackerSide: {
      isTailwind: fieldData.tailwind_attacker ?? false,
    },
    defenderSide: {
      isTailwind: fieldData.tailwind_defender ?? false,
    },
  });
}

function buildPokemon(data) {
  return new Pokemon(gen, data.species, {
    level: data.level ?? 50,
    item: data.item ?? undefined,
    ability: data.ability ?? undefined,
    nature: data.nature ?? "Hardy",
    evs: data.evs
      ? {
          hp: data.evs.hp ?? 0,
          atk: data.evs.atk ?? 0,
          def: data.evs.def ?? 0,
          spa: data.evs.spa ?? 0,
          spd: data.evs.spd ?? 0,
          spe: data.evs.spe ?? 0,
        }
      : undefined,
    boosts: data.boosts
      ? {
          atk: data.boosts.atk ?? 0,
          def: data.boosts.def ?? 0,
          spa: data.boosts.spa ?? 0,
          spd: data.boosts.spd ?? 0,
          spe: data.boosts.spe ?? 0,
        }
      : undefined,
    teraType: data.tera_type ?? undefined,
    status: data.status ?? undefined,
    curHP: data.hp_percent != null
      ? Math.floor(data.hp_percent * 100)
      : undefined,
  });
}

function runCalc(request) {
  try {
    const attacker = buildPokemon(request.attacker);
    const defender = buildPokemon(request.defender);
    const move = new Move(gen, request.move);
    const field = buildField(request.field ?? {});

    const result = calculate(gen, attacker, defender, move, field);
    const range = result.damage;

    const minDmg = Array.isArray(range) ? Math.min(...range) : range;
    const maxDmg = Array.isArray(range) ? Math.max(...range) : range;
    const defenderHP = defender.maxHP();

    const koChance = result.kochance?.n ?? 0;
    const isOHKO = minDmg >= defenderHP;
    const is2HKO = !isOHKO && minDmg * 2 >= defenderHP;

    return {
      attacker: request.attacker.name,
      defender: request.defender.name,
      move: request.move,
      damage_range: [minDmg, maxDmg],
      defender_max_hp: defenderHP,
      ko_chance: koChance,
      is_ohko: isOHKO,
      is_2hko: is2HKO,
      error: null,
    };
  } catch (err) {
    return {
      attacker: request.attacker?.name ?? "unknown",
      defender: request.defender?.name ?? "unknown",
      move: request.move ?? "unknown",
      damage_range: [0, 0],
      ko_chance: 0,
      is_ohko: false,
      is_2hko: false,
      error: err.message,
    };
  }
}

let inputData = "";

process.stdin.setEncoding("utf8");

process.stdin.on("data", (chunk) => {
  inputData += chunk;
});

process.stdin.on("end", () => {
  try {
    const requests = JSON.parse(inputData);
    const results = requests.map(runCalc);
    process.stdout.write(JSON.stringify(results));
  } catch (err) {
    process.stdout.write(JSON.stringify({ error: err.message }));
    process.exit(1);
  }
});