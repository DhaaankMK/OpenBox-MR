"""Catálogo de itens do OpenBox MR: objetos, criaturas, armas, chapéus/acessórios e ferramentas."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Tuple

CATEGORIES: List[Tuple[str, str, str]] = [   # (id, rótulo, ícone)
    ("objetos", "Objetos", "cube"),
    ("criaturas", "Criaturas", "hand"),
    ("armas", "Armas", "bolt"),
    ("chapeus", "Chapéus", "crown"),
    ("ferramentas", "Ferramentas", "gear"),
]


@dataclass(frozen=True)
class Item:
    id: str
    name: str
    cat: str
    desc: str = ""
    kind: str = "body"            # body | creature | weapon | hat | accessory | tool
    r: float = 32.0               # raio físico (px)
    density: float = 1.0
    bounce: float = 1.0           # multiplicador do quique global
    gscale: float = 1.0           # multiplicador da gravidade (negativo = flutua)
    hp: int = 1
    color: Tuple[int, int, int] = (200, 220, 255)
    tags: frozenset = field(default_factory=frozenset)
    attract: Tuple[float, float] = (0.0, 0.0)   # (alcance, força) para ímãs/buracos negros


def _t(*tags):
    return frozenset(tags)


_ALL: List[Item] = [
    # ---------------------------------------------------------------- objetos
    Item("orb", "Esfera Neon", "objetos", "Esfera de vidro holográfico.", r=32, color=(40, 215, 255), tags=_t("round")),
    Item("basketball", "Bola de Basquete", "objetos", "Quica bastante.", r=34, bounce=1.12, color=(238, 118, 30), tags=_t("round")),
    Item("soccer", "Bola de Futebol", "objetos", "Clássica.", r=34, bounce=0.92, color=(240, 240, 245), tags=_t("round")),
    Item("bowling", "Bola de Boliche", "objetos", "Pesadíssima: derruba tudo.", r=36, density=3.2, bounce=0.35, color=(40, 64, 150), tags=_t("round", "heavy")),
    Item("beachball", "Bola de Praia", "objetos", "Leve e flutuante.", r=44, density=0.25, gscale=0.4, color=(255, 90, 120), tags=_t("round")),
    Item("spring", "Bola Mola", "objetos", "Quique absurdo.", r=28, bounce=1.45, color=(90, 255, 120), tags=_t("round")),
    Item("pumpkin", "Abóbora", "objetos", "Estoura com impacto forte.", r=38, density=1.3, bounce=0.45, hp=2, color=(255, 140, 30), tags=_t("round", "breakable")),
    Item("cube", "Cubo Neon", "objetos", "Cubo de vidro holográfico.", r=34, color=(190, 110, 255), tags=_t("box")),
    Item("crate", "Caixote", "objetos", "Quebra com pancadas fortes.", r=37, density=1.4, bounce=0.3, hp=4, color=(176, 124, 68), tags=_t("box", "breakable")),
    Item("dice", "Dado", "objetos", "Role a sorte.", r=30, bounce=0.6, color=(245, 245, 250), tags=_t("box")),
    Item("ice", "Cubo de Gelo", "objetos", "Frio e escorregadio.", r=32, bounce=0.5, hp=2, color=(170, 235, 255), tags=_t("box", "breakable")),
    Item("anvil", "Bigorna", "objetos", "Cai como uma pedra.", r=34, density=6.0, bounce=0.1, color=(120, 128, 150), tags=_t("heavy")),
    Item("barrel", "Barril Explosivo", "objetos", "Explode com impacto ou tiro.", r=36, density=1.2, bounce=0.35, hp=2, color=(220, 60, 50), tags=_t("explosive", "box")),
    Item("tnt", "TNT", "objetos", "Muito instável.", r=34, bounce=0.3, color=(235, 60, 60), tags=_t("explosive", "box")),
    Item("bomb", "Bomba", "objetos", "Explode com impacto forte.", r=32, bounce=0.4, color=(150, 160, 200), tags=_t("explosive", "round")),
    Item("grenade", "Granada", "objetos", "Explode 2,5 s depois de solta.", r=24, density=1.1, bounce=0.4, color=(90, 140, 70), tags=_t("explosive", "timed", "round")),
    Item("rocket", "Foguete de Festa", "objetos", "Solte para acender: sobe e explode em fogos.", r=22, gscale=0.0, color=(255, 80, 80), tags=_t("rocket")),
    Item("star", "Estrela", "objetos", "Facetada e brilhante.", r=30, color=(255, 220, 60), tags=_t("round")),
    Item("heart", "Coração", "objetos", "Cura a base em Sobrevivência.", r=30, color=(255, 90, 150), tags=_t("round", "heal")),
    Item("coin", "Moeda", "objetos", "Gira e brilha.", r=20, density=0.7, bounce=0.8, color=(255, 200, 40), tags=_t("round", "coin")),
    Item("gem", "Diamante", "objetos", "Facetas que refletem a luz.", r=26, density=1.5, bounce=0.5, color=(80, 190, 255), tags=_t("round")),
    Item("balloon", "Balão", "objetos", "Flutua até o teto. Estoura!", r=34, density=0.15, gscale=-0.4, color=(255, 70, 90), tags=_t("round", "pops")),
    Item("duck", "Patinho de Borracha", "objetos", "Quack!", r=27, bounce=0.8, color=(255, 214, 40), tags=_t("round", "squeak")),
    Item("magnet", "Ímã", "objetos", "Atrai objetos próximos.", r=26, density=2.0, color=(230, 60, 70), attract=(330.0, 900.0), tags=_t("round")),
    Item("blackhole", "Buraco Negro", "objetos", "Puxa tudo para o centro.", r=30, density=4.0, gscale=0.0, color=(150, 80, 255), attract=(430.0, 1900.0), tags=_t("round", "heavy")),
    Item("target", "Alvo", "objetos", "Aguenta 3 acertos.", r=40, hp=3, color=(255, 72, 92), tags=_t("round", "target")),
    # ---------------------------------------------------------------- criaturas (bots)
    Item("robot", "Robô", "criaturas", "Anda, pula e se assusta fácil.", kind="creature", r=28, hp=60, color=(120, 170, 220), tags=_t("creature")),
    Item("slime", "Slime", "criaturas", "Pula sem parar e adora mãos.", kind="creature", r=30, hp=40, bounce=0.9, color=(90, 230, 120), tags=_t("creature")),
    Item("chick", "Pintinho", "criaturas", "Pequeno, rápido e medroso.", kind="creature", r=18, hp=20, color=(255, 214, 70), tags=_t("creature")),
    Item("alien", "Alien", "criaturas", "Levita e foge de gestos bruscos.", kind="creature", r=28, hp=50, gscale=0.25, color=(130, 255, 170), tags=_t("creature")),
    Item("ghost", "Fantasma", "criaturas", "Flutua e se esconde.", kind="creature", r=30, hp=30, gscale=0.1, density=0.4, color=(210, 230, 255), tags=_t("creature")),
    Item("skeleton", "Esqueleto", "criaturas", "Ossos que rangem.", kind="creature", r=28, hp=40, color=(235, 235, 220), tags=_t("creature")),
    Item("ninja", "Ninja", "criaturas", "Corajoso e ágil.", kind="creature", r=28, hp=50, color=(60, 60, 80), tags=_t("creature")),
    Item("zombie", "Zumbi", "criaturas", "Caminha para o centro da tela.", kind="creature", r=28, hp=30, color=(110, 170, 90), tags=_t("creature", "hostile")),
    Item("zombie_runner", "Zumbi Corredor", "criaturas", "Rápido e frágil.", kind="creature", r=24, hp=20, color=(150, 190, 90), tags=_t("creature", "hostile")),
    Item("zombie_brute", "Zumbi Brutamontes", "criaturas", "Lento e resistente.", kind="creature", r=40, hp=120, density=2.2, color=(90, 130, 90), tags=_t("creature", "hostile")),
    # ---------------------------------------------------------------- armas
    Item("pistol", "Pistola", "armas", "Dedo-pistola: levante o polegar e abaixe.", kind="weapon", color=(200, 210, 230)),
    Item("smg", "Submetralhadora", "armas", "Rajada rápida.", kind="weapon", color=(255, 190, 70)),
    Item("shotgun", "Escopeta", "armas", "7 projéteis por disparo.", kind="weapon", color=(255, 130, 60)),
    Item("sniper", "Rifle de Precisão", "armas", "Atravessa até 3 alvos.", kind="weapon", color=(120, 255, 190)),
    Item("laser", "Raio Laser", "armas", "Feixe contínuo.", kind="weapon", color=(255, 70, 110)),
    Item("rocket_launcher", "Lança-Foguetes", "armas", "Explosão em área.", kind="weapon", color=(255, 160, 40)),
    # ---------------------------------------------------------------- chapéus e acessórios
    Item("tophat", "Cartola", "chapeus", "Elegância total.", kind="hat", color=(30, 30, 40)),
    Item("wizard", "Chapéu de Mago", "chapeus", "Estrelas no tecido.", kind="hat", color=(110, 70, 210)),
    Item("crown", "Coroa", "chapeus", "Para a realeza.", kind="hat", color=(255, 205, 60)),
    Item("cap", "Boné", "chapeus", "Casual.", kind="hat", color=(60, 120, 230)),
    Item("pirate", "Chapéu de Pirata", "chapeus", "Yo-ho-ho.", kind="hat", color=(40, 40, 50)),
    Item("helmet", "Capacete", "chapeus", "Proteção militar.", kind="hat", color=(90, 120, 80)),
    Item("party", "Chapéu de Festa", "chapeus", "Parabéns!", kind="hat", color=(255, 90, 200)),
    Item("horns", "Chifres", "chapeus", "Diabinho.", kind="hat", color=(230, 50, 60)),
    Item("catears", "Orelhas de Gato", "chapeus", "Miau.", kind="hat", color=(60, 60, 70)),
    Item("halo", "Auréola", "chapeus", "Anjo.", kind="hat", color=(255, 235, 120)),
    Item("cowboy", "Chapéu de Cowboy", "chapeus", "Yeehaw.", kind="hat", color=(170, 110, 60)),
    Item("chef", "Chapéu de Chef", "chapeus", "Bon appétit.", kind="hat", color=(250, 250, 250)),
    Item("viking", "Capacete Viking", "chapeus", "Valhalla.", kind="hat", color=(150, 150, 160)),
    Item("santa", "Gorro de Natal", "chapeus", "Ho ho ho.", kind="hat", color=(220, 40, 50)),
    Item("bunny", "Orelhas de Coelho", "chapeus", "Fofo.", kind="hat", color=(250, 200, 220)),
    Item("antennas", "Antenas", "chapeus", "Sinal captado.", kind="hat", color=(120, 255, 200)),
    Item("sunglasses", "Óculos Escuros", "chapeus", "Estilo.", kind="accessory", color=(20, 20, 30)),
    Item("mustache", "Bigode", "chapeus", "Distinto.", kind="accessory", color=(60, 40, 30)),
    Item("clownnose", "Nariz de Palhaço", "chapeus", "Honk.", kind="accessory", color=(255, 50, 60)),
    # ---------------------------------------------------------------- ferramentas
    Item("explosion", "Explosão", "ferramentas", "Explode onde você clicar.", kind="tool", color=(255, 160, 50)),
    Item("lightning", "Raio", "ferramentas", "Atinge o ponto clicado.", kind="tool", color=(190, 220, 255)),
    Item("shockwave", "Onda de Choque", "ferramentas", "Empurra tudo ao redor.", kind="tool", color=(120, 200, 255)),
    Item("eraser", "Borracha", "ferramentas", "Apaga o objeto clicado.", kind="tool", color=(255, 120, 160)),
]

ITEMS: Dict[str, Item] = {i.id: i for i in _ALL}


def by_cat(cat: str) -> List[Item]:
    return [i for i in _ALL if i.cat == cat]


def get(item_id: str) -> Item | None:
    return ITEMS.get(item_id)
