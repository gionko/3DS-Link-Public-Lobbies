# 3DS Link: public lobbies

The public Azahar rooms that [3DS Link](https://github.com/gionko/3DS-Link) shows, and the list of 3DS titles it uses to tell which edition of a game each player has. These rooms are put online by other people and are not part of the project: use them at your own risk.

## Files

| File | What it is | Who changes it |
|---|---|---|
| `public-lobbies.txt` | The list 3DS Link downloads | The `build-list` workflow, never by hand |
| `sources.txt` | The lobby servers to read, one URL per line (each answers `GET /lobby`) | Us |
| `manual.txt` | Rooms we add or rename. A line here wins over a lobby, and is kept even when the room has a password | Us |
| `exclude.txt` | Rooms to leave out, one `address:port` per line | Us |
| `titles.txt` | Every 3DS application title: `id:region:family` | `tools/build_titles.py`, by hand, rarely |
| `twins.txt` | Versions of one game with different product codes (Pokemon X and Y) | Us |

## public-lobbies.txt

Each room is `address:port:name` or `address:port:name:secret`. The name has no colon and at most 64 characters; the secret is everything after the third colon. Lines that begin with `#` carry the date of the list (`#updated`) and of `titles.txt` (`#titles`).

From a lobby only rooms with no password and network version 4 are taken. Private addresses are left out, and a name loses its links and its colons.

The `build-list` workflow runs twice a day and after a push that changes the files above. It commits the list only when the rooms changed, and renews the date once 30 days have gone by without a change, because GitHub turns off the scheduled workflows of a public repository after 60 days without activity. If it was turned off anyway, turn it on again from the Actions tab, or with:

```
gh workflow enable build-list --repo gionko/3DS-Link-Public-Lobbies
```

When every lobby fails, or the rooms fall below half of the last list, nothing is written and the run fails. The list keeps the rooms it had.

## titles.txt

`id` is the low 32 bits of the title id in hex, so an update or a DLC finds its game. `region` is `JPN`, `USA`, `EUR`, `KOR`, `TWN`, or `FREE` when one id is sold in more than one region. `family` is the first three characters of the product code (CTR-P-AQEP gives AQE), so the editions of a game share it; `twins.txt` joins the versions that do not.

It is built on a PC from three public lists, downloaded by hand and not kept here: [hax0kartik/3dsdb](https://github.com/hax0kartik/3dsdb) (eShop), [3dsdb.com](http://3dsdb.com/xml.php) (cartridges) and, for the titles both lack, [ghost-land/3dsdb](https://github.com/ghost-land/3dsdb). After a change, write a new date with `--stamp`: 3DS Link downloads the list again only when the date changes.

```
python3 tools/build_titles.py --hax <folder of list_*.json> --scene releases.xml --ghost title_catalog.json --stamp YYYY-MM-DD
```

Tests of the list builder: `python3 tools/test_build_list.py`.
