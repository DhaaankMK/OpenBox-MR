# OpenBox MR

> **Realidade mista com a sua webcam.** Agarre, arremesse e destrua objetos, bots e zumbis usando só as mãos e o rosto — sem VR, sem sensores, sem nada além de uma câmera.

Feito por **Khyros Studio** (autor: DhaaankMK) · Gratuito · Windows / Linux / macOS

![status](https://img.shields.io/badge/status-beta-orange) ![python](https://img.shields.io/badge/python-3.10--3.12-blue) ![license](https://img.shields.io/badge/licen%C3%A7a-DUMP--L%201.0-lightgrey)

<!-- Coloque aqui prints/GIFs: ![menu](docs/menu.png) -->

## ▶ Como jogar

1. Instale o [Python 3.10, 3.11 ou 3.12](https://www.python.org/downloads/) (no Windows, marque **Add Python to PATH**).
2. Baixe este repositório (ou o zip em **Releases**) e extraia.
3. Dê dois cliques em **`OpenBox.py`** (ou rode `python OpenBox.py`).

Na **primeira** execução ele prepara tudo sozinho (leva alguns minutos): cria o ambiente virtual e instala as dependências. Nas seguintes, abre direto no launcher. Não precisa de administrador.

### O que o `OpenBox.py` faz (transparência)
- Cria a pasta `OpenBox_Data/.venv` (ambiente Python isolado) e roda `pip install -r OpenBox_Data/requirements.txt`.
- Abre o launcher/jogo usando esse ambiente.
- **Não** baixa executáveis, **não** pede privilégios, **não** envia dados para a internet. O código é todo legível nesta pasta.
- A webcam é processada **no seu computador**; nenhum vídeo é gravado ou enviado. As capturas de tela (`F12`) ficam na pasta local `Capturas/`.

## 🎮 Modos
| Modo | O que é |
|---|---|
| **Tutorial** | 12 passos guiados: pinça, arremesso, menu, dedo-pistola, chapéus… |
| **Sandbox** | Crie objetos, bots e armas; agarre, arremesse e destrua sem regras |
| **Practice** | Treino de pontaria: acerte alvos com arremessos, tiros ou punho; combos e power-ups (variante em ondas) |
| **Sobrevivência** | Zumbis em ondas atacam o reator: use armas, a loja de melhorias e até arremesse os zumbis |

## ✋ Gestos
| Gesto | Ação |
|---|---|
| **Pinça** (polegar + indicador) | Clicar e agarrar/arremessar |
| **Dedo-pistola** | Aponte, **levante** o polegar e **abaixe** para atirar |
| **Palma aberta** | Empurra objetos à distância |
| **Punho** | Esmaga objetos próximos |
| **ROCK** (indicador + mindinho, 1 s) | Abre o menu radial de criação |
| **Joinha** | Slow motion |
| **Palmas juntas** | Onda de choque |
| **Duas mãos** no mesmo objeto | Ampliar e girar |
| **Apontar parado** num botão | Clique por permanência |

**Mouse/teclado:** arrastar agarra · botão direito ou `Q` menu radial · `Tab` catálogo · `1`–`8` barra rápida · `X` arma · `Esc` menu · `F11` tela cheia · `F12` captura · `F3` debug.

## 🧩 Conteúdo
Mais de 60 itens: objetos (bolas, caixote, barril explosivo, TNT, granada, balão, ímã, buraco negro…), criaturas com comportamento próprio (robô, slime, pintinho, alien, fantasma, esqueleto, ninja, zumbis), 6 armas, 16 chapéus + acessórios que seguem o seu rosto e ferramentas (explosão, raio, onda de choque, borracha).

## 🧍 Sentado ou em pé
Nos Ajustes (ou no menu inicial): a postura ajusta alcance de agarre, tamanho dos botões, suavização e tolerância da pinça. Sentado: ~60–90 cm da câmera. Em pé: ~1,5–2 m.

## 📐 Especificações
| Item | Detalhe |
|---|---|
| Linguagem | Python 3.10–3.12 (3.13+ usa um Python compatível automaticamente, se instalado) |
| Janela / render | 1280×720 lógicos (escala automática), alvo de 60 FPS, vsync |
| Gráficos e áudio | **pygame-ce** (sprites sombreados pré-renderizados, partículas, brilho aditivo) |
| Visão computacional | **OpenCV** (captura e pré-processamento) |
| Rastreamento | **MediaPipe** Hand Landmarker (2 mãos, 21 pontos) e Face Landmarker (478 pontos, blendshapes) |
| Matemática | **NumPy** |
| Câmera | Qualquer webcam (recomendado 720p/30 fps e boa iluminação) |
| Rastreamento das mãos | Thread própria, filtro One-Euro, IDs estáveis, compensação de latência, resolução adaptativa |
| Física | Motor 2D próprio (colisões, atratores, explosões, mãos como colisores) |
| Arquitetura | `OpenBox.py` (bootstrap) → `OpenBox_Data/openbox` (core, tracking, physics, game, ui, scenes) |
| Configuração | `Configurações.json` (seções em português, editável com o jogo fechado) |
| Requisitos | ~1 GB livre (dependências), CPU de 4 núcleos recomendada |

## 🗂 Estrutura
```
OpenBox.py                 ← execute este
LICENSE.txt
Configurações.json         ← criado ao salvar (não vai para o git)
OpenBox_Data/
  requirements.txt
  assets/                  ← logo, intro, sons e modelos do MediaPipe
  openbox/                 ← código do jogo
  tests/                   ← testes (sem webcam/janela)
```

## 🛠 Problemas comuns
- **Câmera não abre:** Launcher → Câmera → *Detectar câmeras* / *Pré-visualizar*, ou troque o índice. Feche apps que usam a webcam.
- **Rastreamento falha:** melhore a luz; Ajustes → Rastreio → Qualidade *Ultra*; refaça a *Calibração da pinça*.
- **Lento:** Qualidade *Performance*, resolução 640×480, desligue o rosto (Ajustes → Rosto).
- **Erro na instalação:** use `python OpenBox.py --reinstall`. O MediaPipe precisa de Python 3.10–3.12.
- **Erros do jogo:** ficam em `OpenBox_Data/erros.log` — anexe ao abrir uma issue.

Opções de linha de comando: `--launcher --game --no-camera --mode tutorial|sandbox|practice|survival --reinstall --console --reset-config`.

## ✅ Testes
```
pip install numpy opencv-python-headless
python -m unittest discover -s OpenBox_Data/tests
python OpenBox_Data/tests/smoke_headless.py
```
> O projeto está em **beta** e ainda foi pouco testado em câmeras diferentes. Relatos de bugs são muito bem-vindos!

## 📜 Licença e créditos
© 2026 Khyros Studio · DhaaankMK — licença **DUMP-L** (veja [`LICENSE.txt`](LICENSE.txt)). Bibliotecas e modelos de terceiros: [`THIRD_PARTY_NOTICES.md`](THIRD_PARTY_NOTICES.md).
