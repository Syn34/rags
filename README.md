# RiftApartGS

A mod for **Ratchet & Clank: Rift Apart (PC)**. In **New Game+ (Challenge Mode)**, picking up the
Blast Pistol in the Hall of Heroes at the start of the game also gives you the **Hoverboots** and
**Phantom Dash**.

## Install

1. Get [Ripped Apart](https://github.com/chaoticgd/ripped_apart) and open `modmanager.exe`.
2. Put `RiftApartGS.rcmod` in the game's `mods` folder (or use **Open Mods Folder**).
3. Close the game, click **Refresh**, click the **RiftApartGS.rcmod** row so it's highlighted,
   then click **Install Mods**. It should report 1 mod installed.
4. Start the game, load an NG+ save from before the Hall of Heroes, and pick up the pistol.

To uninstall, deselect the mod and click **Install Mods** again.

> **After a game update:** delete `toc.BAK` in the game folder before installing mods. Ripped Apart
> always rebuilds from `toc.BAK`, and an outdated backup crashes the game at startup.

## Notes

- The gadgets stay with you. The later story pickups check your inventory first: Savali completes
  its Hoverboots objective immediately if you already own them, and the Nefarious City Omniglove
  cutscene continues the story regardless of whether the item could be added.
- Only the New Game+ branch is changed. A normal playthrough is untouched.

## How it works

The pickup isn't driven by an equipment loadout. It's a script in the level file
`i29_malinon_intro_gp_parade_hall_of_heroes.zone`. When you grab the pistol, a `GetDifficultyAction`
node branches:

- **NotChallenge** → `AddToInventoryAction` (Burst Pistol)
- **Challenge** → the rest of the NG+ sequence; nothing is added, since you already own the weapon

The mod adds two `AddToInventoryAction` nodes to the Challenge branch: `gdgt_hoverboots_item.config`,
then `gdgt_versaglove_item.config` (the Omniglove, which is Phantom Dash in-game). Both target the
Hero actor, and the original NG+ sequence continues afterwards on both `Success` and `InventoryFull`.

## Building from your own game files

```
pip install lz4
python tools/build_rags.py "C:/Program Files (x86)/Steam/steamapps/common/Ratchet & Clank - Rift Apart" RiftApartGS.rcmod
```

The game folder must have an unmodded `toc`, or pass `--toc` pointing at a clean copy.

### Tools

| File | What it does |
| --- | --- |
| `tools/build_rags.py` | Extracts the Hall of Heroes level from the game, patches its script, and writes the `.rcmod` |
| `tools/ratoc.py` | Reads the game's `toc` (asset index) and computes asset path hashes |
| `tools/radag.py` | Reads the `dag` dependency graph (asset names and what references what) |
| `tools/racfg.py` | Parses and re-serializes the binary "Config Built File" format used by configs and script node data |
| `tools/zonegraph.py` | Dumps script nodes in a `.zone` that touch the gadgets; `--exe RiftApart.exe` resolves type and pin names |

#### Level script format notes (`.zone`)

- **Node table** (lump `0x5E54ACCF`): 40-byte records `u64 id, u64 id, u16 incoming_exec_count,
  u16 exec_start, u16 exec_count, u16 data_start, u16 data_count, u16 type_index,
  u32 type_hash, u32 config_offset, u32 config_size`.
- **Links** (lump `0xBEAB52E7`): 12-byte entries `u32 output_pin_hash, u32 target_node, u32 target_pin_hash`,
  grouped by source node.
- **Node config pool** (lump `0x2300D240`): one "Config Built File" tree per node.
- Names (node types, pins, config keys) use Insomniac's CRC32: initial value `0xEDB88320`, no final XOR.

## Credits

- Format reference and the CRC-64 table come from [Ripped Apart](https://github.com/chaoticgd/ripped_apart)
  by chaoticgd (MIT).
