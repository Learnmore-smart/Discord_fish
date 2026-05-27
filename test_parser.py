import re

class GameState:
    def __init__(self):
        self.balance = 0
        self.level = 0
        self.bait_amount = 0
        self.bait_name = ""
        self.unowned_items = [] # list of dicts: {'name': 'Heavy Rod', 'price': 100000, 'type': 'rod'}
        self.available_baits = []

    def parse_profile(self, text):
        bal_match = re.search(r'Balance:\s*\$([\d,]+)', text)
        if bal_match:
            self.balance = int(bal_match.group(1).replace(',', ''))

        lvl_match = re.search(r'Level\s+(\d+)', text)
        if lvl_match:
            self.level = int(lvl_match.group(1))

        # "Bait: :bait_magic: Magic Bait (632)"
        # Sometimes there's no bait
        bait_match = re.search(r'Bait:(.*?)(?:\n|$)', text)
        if bait_match:
            bait_line = bait_match.group(1)
            b = re.search(r':([a-z_]+):\s*(.*?)\s*\((\d+)\)', bait_line)
            if b:
                self.bait_name = b.group(2).strip()
                self.bait_amount = int(b.group(3))

    def parse_shop(self, text, category=""):
        if "Your balance:" in text:
            bal_match = re.search(r'Your balance:\s*\$([\d,]+)', text)
            if bal_match:
                self.balance = int(bal_match.group(1).replace(',', ''))

        if category == "bait":
            # Bait shop has lines like: ":bait_magic: Magic Bait - $250. You own: 595"
            baits = re.findall(r':[a-z_]+:\s*(.+?)\s*-\s*\$([\d,]+)\.', text)
            for name, price in baits:
                self.available_baits.append({
                    'name': name.strip(),
                    'price': int(price.replace(',', ''))
                })
        else:
            # Format 1: :slug: Name - $Price (/buy Name)
            items = re.findall(r':[a-z_]+:\s*(.+?)\s*-\s*\$([\d,]+)', text)
            for name, price in items:
                self.unowned_items.append({
                    'name': name.strip(),
                    'price': int(price.replace(',', '')),
                    'type': category
                })

            # Format 2: 10/12 Upgrade Name - $Price
            upgrades = re.findall(r'\d+/\d+\s+(.+?)\s*-\s*\$([\d,]+)', text)
            for name, price in upgrades:
                self.unowned_items.append({
                    'name': name.strip(),
                    'price': int(price.replace(',', '')),
                    'type': category
                })

    def get_best_purchase(self):
        if self.unowned_items:
            self.unowned_items.sort(key=lambda x: x['price'])
            cheapest = self.unowned_items[0]
            if self.balance >= cheapest['price']:
                return cheapest
        return None

def main():
    gs = GameState()

    prof = '''Inventory of Learnmore_smart
Clan: Just sleep faster
Balance: $48,492,925.
Level 148, 128,713/885,000 XP to next level.
Currently using :golden_rod: Golden Rod.
Current biome: :biome_ocean: Ocean
Bait: :bait_magic: Magic Bait (632)
'''
    gs.parse_profile(prof)
    print("Prof:", gs.balance, gs.level, gs.bait_name, gs.bait_amount)

    shop = '''Fishing Rod Shop
Your balance: $48,495,662

:plastic_rod: Plastic Rod - OWNED
Basic starter rod.
:heavy_rod: Heavy Rod - $100,000 (/buy Heavy Rod)
Doesn't catch...'''
    gs.parse_shop(shop, "rods")

    shop2 = '''10/12 Worker Motivation - $200,000,000
Increases amount of fish caught by workers by 10%.
3/5 Experienced - $50,000,000
10/10 Better Dailies - MAX'''
    gs.parse_shop(shop2, "upgrades")

    shop3 = ''':bait_magic: Magic Bait - $250. You own: 595'''
    gs.parse_shop(shop3, "bait")

    print("Unowned:", gs.unowned_items)
    print("Baits:", gs.available_baits)
    print("Best buy:", gs.get_best_purchase())

main()
