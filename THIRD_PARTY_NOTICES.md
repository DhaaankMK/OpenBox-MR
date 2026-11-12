# Avisos de terceiros (Third-Party Notices)

Este arquivo lista o que **não foi criado pela Khyros Studio** e é usado no OpenBox MR, com a licença de cada item.
É uma prática padrão: serve para dar crédito e cumprir as exigências dessas licenças. As licenças abaixo são as informadas
pelos próprios projetos — confira nos sites oficiais antes de qualquer distribuição comercial.

## Bibliotecas (instaladas via `pip`, não incluídas neste repositório)
| Biblioteca | Uso | Licença |
|---|---|---|
| [pygame-ce](https://pyga.me/) | janela, gráficos, áudio, entrada | LGPL-2.1 |
| [OpenCV (opencv-python)](https://opencv.org/) | captura e processamento de imagem | Apache-2.0 (o empacotamento `opencv-python` é MIT) |
| [MediaPipe](https://github.com/google-ai-edge/mediapipe) | rastreamento de mãos e rosto | Apache-2.0 |
| [NumPy](https://numpy.org/) | cálculo numérico | BSD-3-Clause |

## Modelos incluídos em `OpenBox_Data/assets/models/`
| Arquivo | Origem | Licença |
|---|---|---|
| `hand_landmarker.task` | Google MediaPipe (Hand Landmarker) | Apache-2.0 |
| `face_landmarker.task` | Google MediaPipe (Face Landmarker) | Apache-2.0 |

## Sons em `OpenBox_Data/assets/sounds/`
`click.mp3`, `erro.mp3`, `sucesso.mp3` e `notificacao.wav` são sons curtos de estilo "sistema antigo do Windows", obtidos pelo autor em
um site de sons gratuitos e usados **apenas de forma não comercial e gratuita**. Eles podem ter direitos de terceiros. Se você é titular dos
direitos e deseja a remoção, abra uma *issue* e o arquivo será retirado. Todos os demais sons do jogo são **sintetizados em código** (sem arquivos).

## Criação própria (Khyros Studio)
Logo, vídeo de introdução, código-fonte, interface e todos os desenhos de objetos/criaturas/chapéus (gerados por código) — licença DUMP-L (veja `LICENSE.txt`).
