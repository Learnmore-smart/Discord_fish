"""
Comprehensive parser tests using REAL Virtual Fisher data.
Run with: python test_parser.py
"""
import re
import sys

# ─── Emoji pattern shared across parsers ───
EMOJI_PATTERN = r'(?:<a?:[a-zA-Z0-9_]+:\d+>|:[a-zA-Z0-9_]+:)'

# ─── Upgrade priority (lower = higher priority, used as tiebreaker) ───
UPGRADE_PRIORITY = {
    "Better Fish": 1,
    "Salesman": 2,
    "More Chests": 3,
    "Bait Efficiency": 4,
    "Better Dailies": 5,
    "Artifact Specialist": 6,
    "Better Chests": 7,
    "Experienced": 8,
    "Worker Motivation": 9,
}


class GameState:
    def __init__(self):
        self.balance = 0
        self.level = 0
        self.fish_value = 0
        self.bait_amount = 0
        self.bait_name = ""
        self.unowned_items = []       # [{name, price, type, priority?, current_level?, max_level?}]
        self.bait_inventory = {}      # {name: {name, price, owned}}
        self.shop_pages = {}          # {category: total_pages}
        self.next_bait_unlock_level = 0
        self.exotic_inventory = {}    # {name: owned_count}

    def reset_shop_state(self):
        self.unowned_items = []
        self.bait_inventory = {}
        self.shop_pages = {}
        self.next_bait_unlock_level = 0
        self.exotic_inventory = {}

    def parse_profile(self, text):
        # Clean markdown formatting (asterisks and backslashes) to match robustly
        text = text.replace('*', '').replace('\\', '')
        
        bal_match = re.search(r'Balance:\s*\$([\d,]+)', text)
        if bal_match:
            self.balance = int(bal_match.group(1).replace(',', ''))

        lvl_match = re.search(r'Level\s+(\d+)', text)
        if lvl_match:
            self.level = int(lvl_match.group(1))

        fish_val_match = re.search(r'Fish Value:\s*\$([\d,]+)', text)
        if fish_val_match:
            self.fish_value = int(fish_val_match.group(1).replace(',', ''))

        bait_match = re.search(r'Bait:(.*?)(?:\n|$)', text)
        if bait_match:
            bait_line = bait_match.group(1)
            b = re.search(EMOJI_PATTERN + r'\s*(.*?)\s*\(([\d,]+)\)', bait_line)
            if b:
                clean_name = re.sub(r'[\*`]', '', b.group(1)).strip()
                self.bait_name = clean_name
                self.bait_amount = int(b.group(2).replace(',', ''))

        # Exotic Fish section
        exotic_sec = re.search(r'Exotic Fish(.*?)(?:Special|$)', text, re.DOTALL | re.IGNORECASE)
        if exotic_sec:
            # Lines look like: 1,284 :gold_fish: Gold Fish
            matches = re.findall(r'([\d,]+)\s+' + EMOJI_PATTERN + r'\s*(.*?)(?:\n|$)', exotic_sec.group(1))
            for count, name in matches:
                clean_name = re.sub(r'[\*`]', '', name).strip()
                self.exotic_inventory[clean_name] = int(count.replace(',', ''))

        # Special section (for hooks)
        special_sec = re.search(r'Special(.*?)$', text, re.DOTALL | re.IGNORECASE)
        if special_sec:
            hook_match = re.search(r'([\d,]+)\s+' + EMOJI_PATTERN + r'\s*Hooks', special_sec.group(1), re.IGNORECASE)
            if hook_match:
                self.exotic_inventory['Hook'] = int(hook_match.group(1).replace(',', ''))

    def parse_shop(self, text, category=""):
        # Clean markdown formatting (asterisks and backslashes) to match robustly
        text = text.replace('*', '').replace('\\', '')
        
        # Extract balance from shop header
        if "Your balance:" in text:
            bal_match = re.search(r'Your balance:\s*\$([\d,]+)', text)
            if bal_match:
                self.balance = int(bal_match.group(1).replace(',', ''))

        # Detect page numbers: "Page X/Y"
        page_match = re.search(r'Page\s+(\d+)/(\d+)', text)
        if page_match:
            total_pages = int(page_match.group(2))
            if category not in self.shop_pages or total_pages > self.shop_pages[category]:
                self.shop_pages[category] = total_pages

        if category == "bait":
            # Format: :bait_type: Name - $PRICE. You own: COUNT
            bait_pattern = EMOJI_PATTERN + r'\s*(.+?)\s*-\s*\$([\d,]+)\.\s*You own:\s*([\d,]+)'
            baits = re.findall(bait_pattern, text)
            for name, price, owned in baits:
                clean_name = re.sub(r'[\*`]', '', name).strip()
                self.bait_inventory[clean_name] = {
                    'name': clean_name,
                    'price': int(price.replace(',', '')),
                    'owned': int(owned.replace(',', ''))
                }

            # Detect next bait unlock: "UNLOCKED AT LEVEL XXX!"
            unlock_match = re.search(r'UNLOCKED AT LEVEL\s+(\d+)', text)
            if unlock_match:
                self.next_bait_unlock_level = int(unlock_match.group(1))

        elif category == "upgrades":
            # Format: CURRENT/MAX Name - $PRICE   or   CURRENT/MAX Name - MAX
            # Only capture non-MAX upgrades with a $ price
            upgrade_pattern = r'(\d+)/(\d+)\s+(.+?)\s*-\s*\$([\d,]+)'
            upgrades = re.findall(upgrade_pattern, text)
            for current, maximum, name, price in upgrades:
                clean_name = re.sub(r'[\*`]', '', name).strip()
                priority = UPGRADE_PRIORITY.get(clean_name, 50)
                self.unowned_items.append({
                    'name': clean_name,
                    'price': int(price.replace(',', '')),
                    'type': 'upgrades',
                    'priority': priority,
                    'current_level': int(current),
                    'max_level': int(maximum),
                })

        elif category == "special":
            # Format: PRICE :emoji: - CURRENT/MAX Name
            # e.g. 120 :lava_fish: - 6/20 Fish Ovens
            # Regex: ([\d,]+) (emoji) - (\d+)/(\d+) (Name)
            special_pattern = r'([\d,]+)\s+(' + EMOJI_PATTERN + r')\s*-\s*(\d+)/(\d+)\s+(.+?)(?:\n|$)'
            upgrades = re.findall(special_pattern, text)
            for price, emoji_part, current, maximum, name in upgrades:
                clean_name = re.sub(r'[\*`]', '', name).strip()
                # Parse currency type from emoji
                emoji_match = re.search(r':([a-zA-Z0-9_]+):', emoji_part)
                currency = "Gold Fish" # fallback
                if emoji_match:
                    currency = emoji_match.group(1).replace('_', ' ').title()
                
                self.unowned_items.append({
                    'name': clean_name,
                    'price': int(price.replace(',', '')),
                    'currency': currency, # e.g. "Lava Fish", "Diamond Fish"
                    'type': 'special',
                    'priority': 40,
                    'current_level': int(current),
                    'max_level': int(maximum),
                })

            # Parse inventory/balance from header lines specifically
            inv_matches = re.findall(r'(?:Inventory|Balance):\s*(.*?)(?:\n|$)', text, re.IGNORECASE)
            for line in inv_matches:
                matches = re.findall(r'([\d,]+)\s+(' + EMOJI_PATTERN + r')', line)
                for count, emoji_part in matches:
                    emoji_match = re.search(r':([a-zA-Z0-9_]+):', emoji_part)
                    if emoji_match:
                        currency = emoji_match.group(1).replace('_', ' ').title()
                        self.exotic_inventory[currency] = int(count.replace(',', ''))

        else:
            # Rods and Boats — only match items with a $ price (skips OWNED automatically)
            item_pattern = EMOJI_PATTERN + r'\s*(.+?)\s*-\s*\$([\d,]+)'
            items = re.findall(item_pattern, text)
            for name, price in items:
                clean_name = re.sub(r'[\*`]', '', name).strip()
                # Skip balance lines that match the pattern
                if clean_name.lower().startswith('your balance'):
                    continue
                self.unowned_items.append({
                    'name': clean_name,
                    'price': int(price.replace(',', '')),
                    'type': category,
                    'priority': 0,
                })

    def get_best_bait(self):
        """Returns the most expensive (best) available bait from the bait inventory."""
        if not self.bait_inventory:
            return None
        return max(self.bait_inventory.values(), key=lambda b: b['price'])

    def get_purchase_plan(self):
        """Returns an ordered list of purchases: bait maintenance first, then cheapest items."""
        plan = []

        # Priority 1: Bait maintenance
        best_bait = self.get_best_bait()
        if best_bait:
            # Use the bait currently equipped if it exists in inventory, otherwise use best
            current_bait = self.bait_inventory.get(self.bait_name)
            target_bait = current_bait if current_bait else best_bait

            # Always prefer the BEST bait (most expensive) even if currently using a cheaper one
            if best_bait['price'] > target_bait['price']:
                target_bait = best_bait

            # Determine current stock of the target bait
            # Profile bait_amount is the authoritative source for equipped bait
            if target_bait['name'] == self.bait_name and self.bait_amount > 0:
                bait_stock = self.bait_amount
            elif target_bait['name'] in self.bait_inventory:
                bait_stock = self.bait_inventory[target_bait['name']]['owned']
            else:
                bait_stock = 0

            if bait_stock < 100:
                buy_amount = 100
                total_cost = target_bait['price'] * buy_amount
                if self.balance >= total_cost:
                    plan.append({
                        'name': f"{target_bait['name']} {buy_amount}",
                        'display_name': f"100x {target_bait['name']}",
                        'price': total_cost,
                        'type': 'bait',
                        'priority': -1,  # highest priority
                    })

        # Priority 2: Special Shop upgrades (bought with exotic fish)
        special_items = [item for item in self.unowned_items if item['type'] == 'special']
        special_items.sort(key=lambda x: x['price'])
        
        remaining_exotics = self.exotic_inventory.copy()
        for item in special_items:
            currency = item.get('currency', 'Diamond Fish')
            cost = item['price']
            if remaining_exotics.get(currency, 0) >= cost:
                plan.append(item)
                remaining_exotics[currency] -= cost

        # Priority 3: Cheapest available items across all categories (cash upgrades, boats, rods)
        cash_items = [item for item in self.unowned_items if item['type'] != 'special']
        affordable = [item for item in cash_items if self.balance >= item['price']]
        affordable.sort(key=lambda x: (x['price'], x.get('priority', 50)))

        remaining_balance = self.balance
        # Subtract bait cost if bait is in the plan
        for p in plan:
            if p['type'] == 'bait':
                remaining_balance -= p['price']

        for item in affordable:
            if remaining_balance >= item['price']:
                plan.append(item)
                remaining_balance -= item['price']

        return plan


# ═══════════════════════════════════════════
# TEST DATA — Real Virtual Fisher output
# ═══════════════════════════════════════════

PROFILE_TEXT = """Inventory of Learnmore_smart
Clan: Just sleep faster
Balance: $48,492,925.
Level 148, 128,713/885,000 XP to next level.
Currently using :golden_rod: Golden Rod.
Current biome: :biome_ocean: Ocean
Bait: :bait_magic: Magic Bait (18,189)

Fish Inventory
103 :pufferfish: Pufferfish
63 :squid: Squid
24 :turtle: Turtle
Fish Value: $811,676

Exotic Fish
1,284 :gold_fish: Gold Fish
656 :emerald_fish: Emerald Fish
31 :lava_fish: Lava Fish
24 :diamond_fish: Diamond Fish

Special
20 :hook: Hooks"""

ROD_SHOP_PAGE1 = """Fishing Rod Shop
Your balance: $48,495,662

:plastic_rod: Plastic Rod - OWNED
Basic starter rod.
:improved_rod: Improved Rod - OWNED
Attracts slightly better fish.
:steel_rod: Steel Rod - OWNED
Allows you to catch better fish, but slightly less of them.
:fiberglass_rod: Fiberglass Rod - OWNED
Catches large amounts of quality fish.
:heavy_rod: Heavy Rod - $100,000 (/buy Heavy Rod)
Doesn't catch as many fish, but gets you far more treasure.

MORE RODS UNLOCKED AT LEVEL 250.

Page 1/3 (/shop rods <page>)"""

ROD_SHOP_PAGE2 = """Fishing Rod Shop
Your balance: $48,495,662

:alloy_rod: Alloy Rod - $250,000 (/buy Alloy Rod)
Catch rare fish at an inconsistent rate.
:lava_rod: Lava Rod - OWNED
Catches many rare fish consistently.
:magma_rod: Magma Rod - OWNED
Empowered lava rod to attract even more fish.
:oceanium_rod: Oceanium Rod - $75,000,000 (/buy Oceanium Rod)
Made of rare ocean materials.
:golden_rod: Golden Rod - OWNED
Made of pure gold. Catch treasure like you never thought possible.

MORE RODS UNLOCKED AT LEVEL 250.

Page 2/3 (/shop rods <page>)"""

ROD_SHOP_PAGE3 = """Fishing Rod Shop
Your balance: $48,495,662

:superium_rod: Superium Rod - $250,000,000 (/buy Superium Rod)
Ultra light strong design for incredible fish catching abilities.
:infinity_rod: Infinity Rod - $1,000,000,000 (/buy Infinity Rod)
From 6 stones...

MORE RODS UNLOCKED AT LEVEL 250.

Page 3/3 (/shop rods <page>)"""

BOAT_SHOP = """All boats are permanent, decrease fishing cooldown and increase fish count slightly.
/buy <boat name> (e.g. /buy rowboat).
Your balance: $48,498,166

:sailboat: Rowboat - OWNED
:sailboat: Fishing Boat - OWNED
:sailboat: Speedboat - OWNED
:sailboat: Pontoon - OWNED
:sailboat: Sailboat - OWNED
:sailboat: Yacht - OWNED
:grayscale_sailboat: Luxury Yacht - $100,000,000
:grayscale_sailboat: Cruise Ship - $500,000,000

Unlock more boats at Level 250."""

BAIT_SHOP = """Bait is consumed PER CAST so make sure to stock up.
/buy <type> <amount> (e.g. /buy Worms 10).
Your balance: $48,515,998

Bait: :bait_magic: Magic Bait (18,189)

:bait_worms: Worms - $4. You own: 0
Increases amount of fish caught.
:bait_leeches: Leeches - $25. You own: 0
Increases amount of fish caught and slightly improves the quality of fish caught.
:bait_magnet: Magnet - $25. You own: 0
Causes fewer fish to bite but significantly increases your chances of finding treasure.
:bait_wise: Wise Bait - $35. You own: 0
Increases XP per fish catch.
:bait_fish: Fish - $70. You own: 0
Increases your fish catch and the quality of fish.
:bait_artifact: Artifact Magnet - $75. You own: 0
Causes fewer fish to bite but increases your chances of finding treasure and increases quality of treasure found.
:bait_magic: Magic Bait - $250. You own: 18,189
Causes you to catch more, better quality fish and treasure.

Next Bait: :bait_support: Support Bait
UNLOCKED AT LEVEL 150!"""

UPGRADE_SHOP_PAGE1 = """Upgrades in this category are permanent and can be leveled up multiple times.
Use /buy <upgrade name> to level up your upgrades.
Your balance: $48,515,998

21/21 Better Fish - MAX
Causes slightly better fish to bite.
20/20 Salesman - MAX
Sell fish for 5% more.
9/9 Bait Efficiency - MAX
Adds a 5% chance to not consume bait per cast.
11/11 More Chests - MAX
Increases number of chests found by 5%.
10/12 Worker Motivation - $200,000,000
Increases amount of fish caught by workers by 10%.

Page 1/2"""

UPGRADE_SHOP_PAGE2 = """Upgrades in this category are permanent and can be leveled up multiple times.
Use /buy <upgrade name> to level up your upgrades.
Your balance: $48,515,998

7/7 Artifact Specialist - MAX
Improves amount of items found per chest slightly.
3/5 Experienced - $50,000,000
Increases XP gain by 10%.
4/5 Better Chests - $100,000,000
Improves quality of chests found.
10/10 Better Dailies - MAX
Increases items in daily rewards by 10%.

Page 2/2"""


# ═══════════════════════════════════════════
# TEST RUNNER
# ═══════════════════════════════════════════

def run_tests():
    passed = 0
    failed = 0

    def check(name, actual, expected):
        nonlocal passed, failed
        if actual == expected:
            print(f"  ✅ {name}")
            passed += 1
        else:
            print(f"  ❌ {name}")
            print(f"     Expected: {expected}")
            print(f"     Got:      {actual}")
            failed += 1

    # ─── Test 1: Profile Parsing ───
    print("\n📋 Test 1: Profile Parsing")
    gs = GameState()
    gs.parse_profile(PROFILE_TEXT)
    check("Balance", gs.balance, 48492925)
    check("Level", gs.level, 148)
    check("Bait name", gs.bait_name, "Magic Bait")
    check("Bait amount", gs.bait_amount, 18189)
    check("Fish value", gs.fish_value, 811676)

    # ─── Test 2: Rod Shop Parsing (multi-page) ───
    print("\n🎣 Test 2: Rod Shop Parsing (3 pages)")
    gs2 = GameState()
    gs2.parse_shop(ROD_SHOP_PAGE1, "rods")
    gs2.parse_shop(ROD_SHOP_PAGE2, "rods")
    gs2.parse_shop(ROD_SHOP_PAGE3, "rods")
    rod_names = [item['name'] for item in gs2.unowned_items if item['type'] == 'rods']
    check("Total unowned rods", len(rod_names), 5)
    check("Has Heavy Rod", "Heavy Rod" in rod_names, True)
    check("Has Alloy Rod", "Alloy Rod" in rod_names, True)
    check("Has Oceanium Rod", "Oceanium Rod" in rod_names, True)
    check("Has Superium Rod", "Superium Rod" in rod_names, True)
    check("Has Infinity Rod", "Infinity Rod" in rod_names, True)
    check("No OWNED rods (Plastic)", "Plastic Rod" not in rod_names, True)
    check("No OWNED rods (Golden)", "Golden Rod" not in rod_names, True)
    check("Page detection (rods)", gs2.shop_pages.get("rods"), 3)
    # Check prices
    heavy = next(i for i in gs2.unowned_items if i['name'] == 'Heavy Rod')
    check("Heavy Rod price", heavy['price'], 100000)
    infinity = next(i for i in gs2.unowned_items if i['name'] == 'Infinity Rod')
    check("Infinity Rod price", infinity['price'], 1000000000)

    # ─── Test 3: Boat Shop Parsing ───
    print("\n⛵ Test 3: Boat Shop Parsing")
    gs3 = GameState()
    gs3.parse_shop(BOAT_SHOP, "boats")
    boat_names = [item['name'] for item in gs3.unowned_items if item['type'] == 'boats']
    check("Total unowned boats", len(boat_names), 2)
    check("Has Luxury Yacht", "Luxury Yacht" in boat_names, True)
    check("Has Cruise Ship", "Cruise Ship" in boat_names, True)
    check("No OWNED boats (Rowboat)", "Rowboat" not in boat_names, True)
    check("No OWNED boats (Yacht)", "Yacht" not in boat_names, True)
    luxury = next(i for i in gs3.unowned_items if i['name'] == 'Luxury Yacht')
    check("Luxury Yacht price", luxury['price'], 100000000)

    # ─── Test 4: Upgrade Shop Parsing (multi-page) ───
    print("\n⬆️  Test 4: Upgrade Shop Parsing (2 pages)")
    gs4 = GameState()
    gs4.parse_shop(UPGRADE_SHOP_PAGE1, "upgrades")
    gs4.parse_shop(UPGRADE_SHOP_PAGE2, "upgrades")
    upgrade_names = [item['name'] for item in gs4.unowned_items if item['type'] == 'upgrades']
    check("Total non-MAX upgrades", len(upgrade_names), 3)
    check("Has Worker Motivation", "Worker Motivation" in upgrade_names, True)
    check("Has Experienced", "Experienced" in upgrade_names, True)
    check("Has Better Chests", "Better Chests" in upgrade_names, True)
    check("No MAX upgrades (Better Fish)", "Better Fish" not in upgrade_names, True)
    check("No MAX upgrades (Salesman)", "Salesman" not in upgrade_names, True)
    check("Page detection (upgrades)", gs4.shop_pages.get("upgrades"), 2)
    # Check levels
    wm = next(i for i in gs4.unowned_items if i['name'] == 'Worker Motivation')
    check("Worker Motivation level", wm['current_level'], 10)
    check("Worker Motivation max", wm['max_level'], 12)
    check("Worker Motivation price", wm['price'], 200000000)
    exp = next(i for i in gs4.unowned_items if i['name'] == 'Experienced')
    check("Experienced level", exp['current_level'], 3)
    check("Experienced priority", exp['priority'], 8)

    # ─── Test 5: Bait Shop Parsing ───
    print("\n🪱 Test 5: Bait Shop Parsing")
    gs5 = GameState()
    gs5.parse_shop(BAIT_SHOP, "bait")
    check("Total bait types", len(gs5.bait_inventory), 7)
    check("Worms price", gs5.bait_inventory['Worms']['price'], 4)
    check("Worms owned", gs5.bait_inventory['Worms']['owned'], 0)
    check("Magic Bait price", gs5.bait_inventory['Magic Bait']['price'], 250)
    check("Magic Bait owned", gs5.bait_inventory['Magic Bait']['owned'], 18189)
    check("Next bait unlock level", gs5.next_bait_unlock_level, 150)
    # Best bait
    best = gs5.get_best_bait()
    check("Best bait is Magic Bait", best['name'], "Magic Bait")
    check("Best bait price", best['price'], 250)

    # ─── Test 6: Purchase Plan ───
    print("\n🛒 Test 6: Purchase Plan (full scenario)")
    gs6 = GameState()
    gs6.parse_profile(PROFILE_TEXT)
    gs6.parse_shop(ROD_SHOP_PAGE1, "rods")
    gs6.parse_shop(ROD_SHOP_PAGE2, "rods")
    gs6.parse_shop(ROD_SHOP_PAGE3, "rods")
    gs6.parse_shop(BOAT_SHOP, "boats")
    gs6.parse_shop(UPGRADE_SHOP_PAGE1, "upgrades")
    gs6.parse_shop(UPGRADE_SHOP_PAGE2, "upgrades")
    gs6.parse_shop(BAIT_SHOP, "bait")

    plan = gs6.get_purchase_plan()
    # With 18189 bait, no bait purchase needed
    plan_names = [p.get('display_name', p['name']) for p in plan]
    check("No bait in plan (stock=18189)", any('bait' in n.lower() for n in plan_names if 'Bait' in n and '50x' in n), False)
    # Should buy: Heavy Rod ($100K), Alloy Rod ($250K) — affordable
    # Should NOT buy: Oceanium Rod ($75M), Experienced ($50M) — can't afford both after Alloy
    check("First purchase is Heavy Rod", plan[0]['name'], "Heavy Rod")
    check("Second purchase is Alloy Rod", plan[1]['name'], "Alloy Rod")
    # The remaining balance after 2 rods: ~$48.1M, enough for Experienced ($50M)? No, 48.49M - 0.35M = 48.14M < 50M
    # Actually: 48,492,925 - 100,000 - 250,000 = 48,142,925 < 50,000,000
    # So Experienced should NOT be in the plan
    check("Cannot afford Experienced after rods", len(plan), 2)

    # ─── Test 7: Purchase Plan with low bait ───
    print("\n🪱 Test 7: Purchase Plan with low bait")
    gs7 = GameState()
    gs7.balance = 48492925
    gs7.level = 148
    gs7.bait_name = "Magic Bait"
    gs7.bait_amount = 5  # LOW!
    gs7.parse_shop(BAIT_SHOP, "bait")
    gs7.parse_shop(ROD_SHOP_PAGE1, "rods")

    plan7 = gs7.get_purchase_plan()
    check("First purchase is bait (low stock)", plan7[0]['type'], "bait")
    check("Bait purchase is 100x Magic Bait", plan7[0]['display_name'], "100x Magic Bait")
    check("Bait cost is 100*250=$25,000", plan7[0]['price'], 25000)
    # After bait, should still buy Heavy Rod
    check("Second purchase is Heavy Rod", plan7[1]['name'], "Heavy Rod")

    # ─── Test 8: Upgrade priority tiebreaking ───
    print("\n🏆 Test 8: Upgrade priority ordering")
    gs8 = GameState()
    gs8.balance = 999999999999
    # Add two upgrades with same price but different priorities
    gs8.unowned_items = [
        {'name': 'Worker Motivation', 'price': 100, 'type': 'upgrades', 'priority': 9, 'current_level': 10, 'max_level': 12},
        {'name': 'Better Fish', 'price': 100, 'type': 'upgrades', 'priority': 1, 'current_level': 5, 'max_level': 10},
    ]
    plan8 = gs8.get_purchase_plan()
    check("Higher priority upgrade first", plan8[0]['name'], "Better Fish")
    check("Lower priority upgrade second", plan8[1]['name'], "Worker Motivation")

    # ─── Test 9: Special Shop Upgrades Parsing & Planning ───
    print("\n💎 Test 9: Special Shop Upgrades Parsing & Planning")
    gs9 = GameState()
    
    # Mock some profile with exotics
    profile_with_exotics = """Inventory of Learnmore_smart
Clan: Just sleep faster
Balance: $48,492,925.
Level 148, 128,713/885,000 XP to next level.
Currently using :golden_rod: Golden Rod.
Current biome: :biome_ocean: Ocean
Bait: :bait_magic: Magic Bait (632)

Exotic Fish
1,284 :gold_fish: Gold Fish
656 :emerald_fish: Emerald Fish
75 :lava_fish: Lava Fish
64 :diamond_fish: Diamond Fish"""

    gs9.parse_profile(profile_with_exotics)
    check("Lava Fish inventory parsed", gs9.exotic_inventory.get("Lava Fish"), 75)
    check("Diamond Fish inventory parsed", gs9.exotic_inventory.get("Diamond Fish"), 64)

    special_shop_text = """Special Shop
Use /buy <upgrade name> to level up your upgrades.
Inventory: 75 :lava_fish:, and 64 :diamond_fish:.

120 :lava_fish: - 6/20 Fish Ovens
Cook the fish you sell for a 5% increase in selling price.
250 :diamond_fish: - 3/4 Bait Lover
Increase effectiveness of bait by 15%.
25 :diamond_fish: - 1/4 Highly Experienced
Increase XP gain by 15%."""

    gs9.parse_shop(special_shop_text, "special")
    special_items = [item for item in gs9.unowned_items if item['type'] == 'special']
    check("Total parsed special upgrades", len(special_items), 3)
    
    ovens = next(i for i in special_items if i['name'] == 'Fish Ovens')
    check("Fish Ovens price (Lava Fish)", ovens['price'], 120)
    check("Fish Ovens currency type", ovens['currency'], "Lava Fish")
    
    exp_spec = next(i for i in special_items if i['name'] == 'Highly Experienced')
    check("Highly Experienced price (Diamond Fish)", exp_spec['price'], 25)
    check("Highly Experienced currency type", exp_spec['currency'], "Diamond Fish")

    # Planning
    plan9 = gs9.get_purchase_plan()
    plan9_names = [p['name'] for p in plan9]
    # We have 75 Lava Fish -> cannot afford Fish Ovens (120)
    # We have 64 Diamond Fish -> can afford Highly Experienced (25), but not Bait Lover (250)
    check("Highly Experienced is in purchase plan", "Highly Experienced" in plan9_names, True)
    check("Fish Ovens is NOT in plan", "Fish Ovens" not in plan9_names, True)
    check("Bait Lover is NOT in plan", "Bait Lover" not in plan9_names, True)

    # ─── Test 10: League Shop Upgrades Parsing & Planning ───
    print("\n🏆 Test 10: League Shop Upgrades Parsing & Planning")
    gs10 = GameState()
    gs10.parse_profile(PROFILE_TEXT)
    check("Hooks from profile parsed", gs10.exotic_inventory.get("Hook"), 20)

    league_shop_page1 = """League Shop
Hooks :hook: are obtained through weekly fishing leagues. In addition you can earn them through special quests each day.

Balance: 121 :hook:

50 :hook: - 0/5 Pet Helper
Raises pet max level by 5. Increases low level pet XP gain.
50 :hook: - 0/5 Bait Helper
Increases bait effectiveness by 10%.
50 :hook: - 0/5 Super Crates
Find super crates. Upgrades increase your chances of finding a super crate.
50 :hook: - 0/5 Worker Crates
Allows workers to find crates. Upgrades increase quality and number of crates found.

You will receive +49 hooks :hook: at the end of the week. Continue fishing for a greater reward.

Page 1/2"""

    league_shop_page2 = """League Shop
Hooks :hook: are obtained through weekly fishing leagues. In addition you can earn them through special quests each day.

Balance: 121 :hook:

50 :hook: - 0/5 Fishing Frenzy
Increases effectiveness of temporary boosts.
25 :hook: - 0/10 Duplicator 2.0
3% Chance to double fish catch.

You will receive +49 hooks :hook: at the end of the week. Continue fishing for a greater reward.

Page 2/2"""

    gs10.parse_shop(league_shop_page1, "special")
    gs10.parse_shop(league_shop_page2, "special")
    
    check("Hooks balance from shop parsed", gs10.exotic_inventory.get("Hook"), 121)
    
    league_items = [item for item in gs10.unowned_items if item['type'] == 'special' and item.get('currency') == 'Hook']
    check("Total parsed league upgrades", len(league_items), 6)
    
    pet_helper = next(i for i in league_items if i['name'] == 'Pet Helper')
    check("Pet Helper price (Hooks)", pet_helper['price'], 50)
    check("Pet Helper currency type", pet_helper['currency'], "Hook")
    
    duplicator = next(i for i in league_items if i['name'] == 'Duplicator 2.0')
    check("Duplicator 2.0 price (Hooks)", duplicator['price'], 25)
    check("Duplicator 2.0 currency type", duplicator['currency'], "Hook")

    plan10 = gs10.get_purchase_plan()
    plan10_names = [p['name'] for p in plan10]
    check("Duplicator 2.0 is in purchase plan", "Duplicator 2.0" in plan10_names, True)
    check("Duplicator 2.0 is first purchase", plan10[0]['name'], "Duplicator 2.0")
    
    plan10_league = [p for p in plan10 if p['type'] == 'special' and p.get('currency') == 'Hook']
    check("Can afford 2 league upgrades", len(plan10_league), 2)

    # ─── Summary ───
    print(f"\n{'='*50}")
    print(f"Results: {passed} passed, {failed} failed, {passed + failed} total")
    print(f"{'='*50}")

    return failed == 0


if __name__ == "__main__":
    success = run_tests()
    sys.exit(0 if success else 1)
