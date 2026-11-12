"""Tutorial guiado: passos com condição por evento (lógica pura, usada pelo modo Tutorial)."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, List, Optional


@dataclass(frozen=True)
class Step:
    id: str
    title: str
    text: str
    icon: str
    need: str            # nome do evento que conclui o passo
    count: int = 1       # quantas vezes o evento precisa ocorrer
    optional: bool = False


STEPS: List[Step] = [
    Step("hand", "Mostre sua mão", "Coloque a mão aberta diante da câmera, com boa iluminação.", "hand", "hand_seen"),
    Step("pinch", "Faça a pinça", "Junte a ponta do polegar e do indicador. A pinça é o seu clique.", "hand", "pinch", 2),
    Step("grab", "Agarre a esfera", "Pince sobre a esfera e segure para pegá-la.", "orb", "grab"),
    Step("throw", "Arremesse", "Agarre e solte enquanto move a mão rápido para lançar.", "right", "throw"),
    Step("push", "Empurre", "Abra a mão e passe a palma ou os dedos nos objetos para empurrá-los.", "hand", "push"),
    Step("smash", "Esmague com o punho", "Feche o punho perto de um objeto para esmagá-lo.", "fist", "smash"),
    Step("scale", "Duas mãos", "Agarre o caixote com as duas mãos e afaste-as para ampliá-lo.", "up", "scale"),
    Step("menu", "Abra o menu de criação", "Faça o gesto ROCK (indicador + mindinho) por 1 s — ou clique no Catálogo.", "gear", "menu_open"),
    Step("spawn", "Crie algo", "Pince um item do menu: ele nasce na sua mão.", "star", "spawn"),
    Step("shoot", "Dedo-pistola", "Aponte o indicador, LEVANTE o polegar e ABAIXE-O para atirar no alvo.", "bolt", "shoot", 3),
    Step("hat", "Chapéu", "Abra o Catálogo → Chapéus e escolha um. Precisa do rosto visível.", "crown", "hat_equip", 1, True),
    Step("done", "Pronto!", "Você dominou o básico. Explore o Sandbox ou enfrente os zumbis!", "check", "never"),
]


class Tutorial:
    def __init__(self, on_step: Optional[Callable[[Step], None]] = None, on_finish: Optional[Callable[[], None]] = None):
        self.idx = 0
        self.progress = 0
        self.on_step, self.on_finish = on_step, on_finish
        self.finished = False
        self.done_ids: List[str] = []

    @property
    def step(self) -> Step:
        return STEPS[min(self.idx, len(STEPS) - 1)]

    @property
    def fraction(self) -> float:
        return min(1.0, self.idx / (len(STEPS) - 1))

    def event(self, name: str) -> bool:
        """Registra um evento; True se concluiu o passo atual."""
        if self.finished or self.step.need != name:
            return False
        self.progress += 1
        if self.progress >= self.step.count:
            self._advance()
            return True
        return False

    def _advance(self):
        self.done_ids.append(self.step.id)
        if self.on_step:
            self.on_step(self.step)
        self.idx += 1
        self.progress = 0
        if self.step.id == "done":
            self.finished = True
            if self.on_finish:
                self.on_finish()

    def skip(self):
        if not self.finished:
            self._advance()

    def skip_optional(self):
        if self.step.optional:
            self.skip()
