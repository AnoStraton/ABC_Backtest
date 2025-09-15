Backtest ABC Fractals

Ce projet implémente un moteur de backtest basé sur les setups fractals A–B–C, avec gestion du risque et visualisation.
L’objectif est d’analyser la robustesse de la stratégie à travers des métriques de performance, un journal de trades complet, et des graphiques interactifs.

🚀 Fonctionnalités

Détection fractales HH / LH / HL / LL à partir d’un dataset OHLC.

Construction et validation de setups A–B–C.

Exécution des trades avec SL / TP / invalidation, prise en compte des frais.

Gestion de trois modes de risque :

Risque fixe (% du capital initial),

Risque composé (% du capital courant),

Risque daily (% du capital fixé en début de journée).

Calcul de métriques clés :

WinRate (WR),

Profit Factor (PF),

Sharpe Ratio,

SQN,

Max Drawdown (et indices associés).

Agrégations par jour de la semaine et par session (Asie, Londres, New York).

Visualisation :

Chandeliers avec fractals + overlays (SL, TP, PE, invalidations/validations),

Courbes d’équité avec drawdown surligné,

Bar charts par jour et par session.

Export CSV du journal des trades.




Architecture

Le projet est conçu en modules séparés pour plus de clarté et d’évolutivité.

CSV → tools → structure → signals → executor → analytics → visualize → export

module/tools.py → gestion des datasets (I/O, normalisation).

module/structure.py → détection / classification des fractales.

module/signals.py → construction des setups A–B–C (règles de validation).

module/executor.py → exécution des trades (SL/TP, PnL, sizing).

module/analytics.py → calcul des courbes et métriques.

module/visualize.py → tracés des chandeliers, fractals, equity curves.

module/export.py → export des résultats (CSV, figures).

backtest.py → script principal (orchestration du pipeline).




Installation
Dépendances

Le projet nécessite Python 3.10+ et les bibliothèques suivantes :

pandas
numpy
matplotlib
mplfinance
pytz

Installe-les avec :

pip install -r requirements.txt




Utilisation
Lancer un backtest:

python backtest.py


Résultats générés

Plots :

Chandeliers + fractals + segments SL/TP/PE/invalidation.

Equity curves (fixe / composé / daily).

Bar charts par jour et par session.

CSV des trades : trades_<symbole>_<profil>.csv

Logs console : suivi détaillé de l’exécution (DEBUG/INFO).




Paramètres principaux

Les paramètres clés (actuellement dans backtest.py, bientôt centralisés dans config/) :

maximum_candle_between_a_and_c → nb max de bougies entre A et C.

riskratio → ratio R:R (ex: 2 = TP à 2R).

risk_percentage → % du capital risqué par trade.

fees → frais de transaction (ex: 0.0004 = 0.04%).

capital_init → capital initial du backtest.

sessions → plages horaires (UTC) pour Asie / Londres / New York.

trades_filename → nom du fichier CSV de sortie des trades.



Structure des sorties

Trades CSV :
Colonnes : pair, entry_time, exit_time, direction, entry_price, exit_price, SL, TP, pnl_fixed, pnl_compound, pnl_daily, result.

Plots :
Sauvegardés dans reports/figures/.

Métriques :
Sauvegardées dans reports/tables/.


Projet développé par Anostraton
Licence : MIT (modifiable selon tes besoins).


