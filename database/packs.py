import json
from uuid import UUID
from typing import Any
from dataclasses import dataclass

from database.connection import Database


def _parse_jsonb(value) -> dict:
    if value is None:
        return {}
    if isinstance(value, dict):
        return value
    if isinstance(value, str):
        try:
            return json.loads(value)
        except json.JSONDecodeError:
            return {}
    return {}


@dataclass
class AvailablePack:
    id: UUID
    short_name: str
    name: str
    pack_file: dict[str, Any]
    number_of_themes: int
    available_themes_count: int
    available_theme_indices: list[int]


async def create_pack(short_name: str, name: str, pack_file: dict[str, Any], number_of_themes: int) -> UUID:
    pool = Database.get_pool()
    sql = Database.load_sql("packs/create_pack.sql")
    
    async with pool.acquire() as conn:
        row = await conn.fetchrow(sql, short_name, name, json.dumps(pack_file), number_of_themes)
        return row['id']


async def get_pack_by_short_name(short_name: str) -> dict | None:
    pool = Database.get_pool()
    sql = Database.load_sql("packs/get_pack_by_short_name.sql")
    
    async with pool.acquire() as conn:
        row = await conn.fetchrow(sql, short_name)
        if not row:
            return None
        result = dict(row)
        result['pack_file'] = _parse_jsonb(result.get('pack_file'))
        return result


async def get_all_packs() -> list[dict]:
    pool = Database.get_pool()
    sql = Database.load_sql("packs/get_all_packs.sql")
    
    async with pool.acquire() as conn:
        rows = await conn.fetch(sql)
        result = []
        for row in rows:
            pack = dict(row)
            pack['pack_file'] = _parse_jsonb(pack.get('pack_file'))
            result.append(pack)
        return result


async def get_player_pack_histories(player_ids: list) -> list[dict]:
    if not player_ids:
        return []
    
    pool = Database.get_pool()
    sql = Database.load_sql("packs/get_player_pack_histories.sql")
    
    async with pool.acquire() as conn:
        rows = await conn.fetch(sql, player_ids)
        return [dict(row) for row in rows]


def format_themes_as_ranges(themes: list[int]) -> str:
    if not themes:
        return ''
    
    sorted_themes = sorted(themes)
    ranges = []
    start = sorted_themes[0]
    end = sorted_themes[0]
    
    for t in sorted_themes[1:]:
        if t == end + 1:
            end = t
        else:
            if start == end:
                ranges.append(str(start))
            else:
                ranges.append(f"{start}-{end}")
            start = t
            end = t
    
    if start == end:
        ranges.append(str(start))
    else:
        ranges.append(f"{start}-{end}")
    
    return ','.join(ranges)


async def update_player_pack_history(player_id: UUID, pack_id: UUID, themes_played: list[int]) -> None:
    if not themes_played:
        return
    
    themes_str = format_themes_as_ranges(themes_played)
    
    pool = Database.get_pool()
    sql = Database.load_sql("packs/upsert_player_pack_history.sql")
    
    async with pool.acquire() as conn:
        await conn.execute(sql, player_id, pack_id, themes_str)


def parse_themes_played(themes_str: str) -> set[int]:
    if not themes_str or not themes_str.strip():
        return set()
    
    played = set()
    for part in themes_str.split(','):
        part = part.strip()
        if '-' in part:
            start, end = part.split('-')
            played.update(range(int(start), int(end) + 1))
        elif part.isdigit():
            played.add(int(part))
    return played


async def get_available_packs_for_players(player_ids: list, themes_needed: int = 6) -> list[AvailablePack]:
    all_packs = await get_all_packs()
    if not all_packs:
        return []
    
    histories = await get_player_pack_histories(player_ids)
    
    pack_player_history: dict[str, dict[str, set[int]]] = {}
    for h in histories:
        pack_id = str(h['pack_id'])
        player_id = str(h['player_id'])
        if pack_id not in pack_player_history:
            pack_player_history[pack_id] = {}
        pack_player_history[pack_id][player_id] = parse_themes_played(h['themes_played'])
    
    available_packs: list[AvailablePack] = []
    
    for pack in all_packs:
        pack_id = str(pack['id'])
        total_themes = pack['number_of_themes']
        
        if total_themes == 0:
            continue
        
        all_theme_indices = set(range(0, total_themes))
        
        themes_played_by_any = set()
        for player_id in player_ids:
            player_id_str = str(player_id)
            if pack_id in pack_player_history and player_id_str in pack_player_history[pack_id]:
                themes_played_by_any.update(pack_player_history[pack_id][player_id_str])
        
        available_themes = all_theme_indices - themes_played_by_any
        
        if len(available_themes) >= themes_needed:
            available_packs.append(AvailablePack(
                id=pack['id'],
                short_name=pack['short_name'],
                name=pack['name'],
                pack_file=pack['pack_file'],
                number_of_themes=total_themes,
                available_themes_count=len(available_themes),
                available_theme_indices=sorted(available_themes)
            ))
    
    available_packs.sort(key=lambda p: p.available_themes_count, reverse=True)
    
    return available_packs
