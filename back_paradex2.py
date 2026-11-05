import module.tools
import module.structure

import matplotlib.pyplot as plt
import mplfinance as mpf
from datetime import datetime
import pandas as pd
import numpy as np
import collections
from pytz import timezone
import csv
import os

"""
Fees
Vitesse de calcul
"""

# ============================================================
# 1) PARAMÈTRES ET IMPORTS
# ============================================================

# Paramètres de base
maximum_candle_between_a_and_c = 60
number_of_break_for_invalidation_on_c = 2

capital_init = 10000

# -----------------------------
# !!! ICI : fees = 0.0004 (0.04%) !!!
# Si vous voulez 0.4%, mettez fees = 0.004
# -----------------------------
fees = 0.0000

riskratio = 2

# Pourcentage de risque (exemple : 1% = 0.01)
risk_percentage = 0.01

# Trois listes de capital distinctes
capital_list_fixed = [capital_init]    # 1) Risque fixe = % * capital_init
capital_list_compound = [capital_init] # 2) Risque composé = % du capital courant
capital_list_daily = [capital_init]    # 3) Risque = % de la balance figée à minuit (ou premier trade du jour)

# Pour la balance quotidienne (approche #3)
day_balance_dict = {}  # key = 'YYYY-mm-dd', value = capital_list_daily[-1] en début de journée

# Autres listes pour stocker signaux, SL, etc.
invalidationabc = []
valid_abc = []
sl_abc = []
pe_abc = []
tp_abc = []

p_point = None

# -----------------------------
# Nouvelle section : Structures de données pour l'analyse
# -----------------------------
# Liste pour stocker les détails des trades
trades = []

# Définir les fuseaux horaires si nécessaire
utc = timezone('UTC')

# Plages horaires des sessions en UTC
sessions = {
    'Asie': {'start': 0, 'end': 8},
    'Londres': {'start': 8, 'end': 16},
    'New York': {'start': 16, 'end': 24}
}

# Nom du fichier CSV pour sauvegarder les trades
trades_filename = 'trades_btcusdperp_m1_360d.csv'  # Vous pouvez changer ce nom selon vos besoins

# ============================================================
# 2) FONCTIONS UTILITAIRES
# ============================================================

def get_daily_balance(date_ts):
    """
    Retourne la balance de référence pour la journée (mode #3).
    - 'date_ts' est un pd.Timestamp (index de df).
    - On stocke la balance journalière dans day_balance_dict.
    """
    day_str = date_ts.strftime('%Y-%m-%d')
    if day_str not in day_balance_dict:
        # On fige la valeur pour ce jour : la dernière valeur de capital_list_daily
        day_balance_dict[day_str] = capital_list_daily[-1]
    return day_balance_dict[day_str]

def calcul_pnl_for_3_modes(win_or_loss_r):
    """
    Calcule le PnL (profit ou perte) pour (1) capital fixe, (2) capital composé, (3) placeholder pour daily.
    win_or_loss_r : ex. +2 pour un TP (2R), -1 pour un SL (1R).
    """
    # 1) Risque fixe
    Rfix = risk_percentage * capital_init
    pnl_fixed = Rfix * win_or_loss_r

    # 2) Risque composé
    Rcomp = risk_percentage * capital_list_compound[-1]
    pnl_compound = Rcomp * win_or_loss_r

    # 3) Daily => placeholder, calculé manuellement dans execution() (car besoin day_balance_start).
    pnl_daily_placeholder = None

    return pnl_fixed, pnl_compound, pnl_daily_placeholder, Rfix, Rcomp

def compute_metrics(capital_list):
    """
    Calcule diverses métriques (WinRate, MaxDD, PF, Sharpe, SQN) sur 'capital_list'.
    Retourne un dict contenant ces métriques + indices du max DD.
    """
    # 1) Win Rate (on suppose "gagnant" si capital_list[i] > capital_list[i-1])
    wins = 0
    for i in range(1, len(capital_list)):
        if capital_list[i] > capital_list[i - 1]:
            wins += 1
    if len(capital_list) > 1:
        total_trades = len(capital_list) - 1
        win_rate = (wins / total_trades) * 100
    else:
        win_rate = 0

    # 2) Max Drawdown (absolu et %)
    peak = capital_list[0]
    max_drawdown_abs = 0
    max_dd_start = 0
    max_dd_end = 0
    temp_start = 0

    for i in range(len(capital_list)):
        if capital_list[i] > peak:
            peak = capital_list[i]
            temp_start = i
        dd_abs = peak - capital_list[i]
        if dd_abs > max_drawdown_abs:
            max_drawdown_abs = dd_abs
            max_dd_start = temp_start
            max_dd_end = i

    base_capital = capital_list[0]
    if base_capital != 0:
        max_drawdown_pct = (max_drawdown_abs / base_capital) * 100
    else:
        max_drawdown_pct = 0

    # 3) Profit Factor
    gains = 0
    losses = 0
    for i in range(1, len(capital_list)):
        diff = capital_list[i] - capital_list[i - 1]
        if diff > 0:
            gains += diff
        elif diff < 0:
            losses += abs(diff)
    if losses == 0:
        profit_factor = float('inf')
    else:
        profit_factor = gains / losses

    # 4) Sharpe ratio (simplifié)
    returns = []
    for i in range(1, len(capital_list)):
        prev = capital_list[i - 1]
        if prev != 0:
            ret = (capital_list[i] / prev) - 1
            returns.append(ret)
    if len(returns) > 1:
        mean_ret = np.mean(returns)
        std_ret = np.std(returns, ddof=1)
        if std_ret == 0:
            sharpe_ratio = float('inf')
        else:
            sharpe_ratio = mean_ret / std_ret * np.sqrt(len(returns))
    else:
        sharpe_ratio = 0

    # 5) SQN (simplifié)
    if len(returns) > 1:
        avg_r = np.mean(returns)
        std_r = np.std(returns, ddof=1)
        if std_r == 0:
            sqn = float('inf')
        else:
            sqn = np.sqrt(len(returns)) * avg_r / std_r
    else:
        sqn = 0

    return {
        'win_rate': win_rate,
        'max_drawdown_abs': max_drawdown_abs,
        'max_drawdown_pct': max_drawdown_pct,
        'profit_factor': profit_factor,
        'sharpe_ratio': sharpe_ratio,
        'sqn': sqn,
        'max_dd_start': max_dd_start,
        'max_dd_end': max_dd_end
    }

def plot_equity_curve_with_metrics(capital_list, approach_name):
    """
    Affiche la courbe de capital, surligne le max drawdown,
    et ajoute un titre contenant les métriques.
    """
    m = compute_metrics(capital_list)
    win_rate = m['win_rate']
    max_dd_pct = m['max_drawdown_pct']
    profit_factor = m['profit_factor']
    sharpe_ratio = m['sharpe_ratio']
    sqn = m['sqn']
    max_dd_start = m['max_dd_start']
    max_dd_end = m['max_dd_end']

    # Plot
    plt.figure(figsize=(10, 6))
    plt.plot(capital_list, label='Capital', color='blue', linewidth=2)

    # Surligner la zone du drawdown max
    plt.axvspan(max_dd_start, max_dd_end, color='red', alpha=0.2, label='Max Drawdown Zone')

    # Ajouter annotation à la fin du DD
    if max_dd_end < len(capital_list):
        dd_y = capital_list[max_dd_end]
        annotation_y = dd_y - (capital_list[0] * 0.05)
        plt.annotate(
            f"DD={max_dd_pct:.2f}%",
            xy=(max_dd_end, dd_y),
            xytext=(max_dd_end, annotation_y),
            arrowprops=dict(facecolor='red', shrink=0.05),
            fontsize=9, color='red'
        )

    # Construction du titre
    metrics_text = (
        f"WinRate={win_rate:.1f}%, "
        f"PF={profit_factor:.2f}, "
        f"Sharpe={sharpe_ratio:.2f}, "
        f"SQN={sqn:.2f}, "
        f"MaxDD={max_dd_pct:.2f}%"
    )
    plt.title(f"{approach_name}\n{metrics_text}", fontsize=12)

    plt.xlabel("Nombre de trades")
    plt.ylabel("Capital")
    plt.legend(loc='best')
    plt.grid(True)
    plt.show()

def categorize_trade(timestamp):
    """
    Catégorise le trade en fonction du jour de la semaine et de la session de trading.
    Retourne le jour (lundi, mardi, ...) et la session (Asie, Londres, New York).
    """
    # Assurez-vous que le timestamp est en timezone UTC
    if timestamp.tzinfo is None:
        timestamp = utc.localize(timestamp)
    else:
        timestamp = timestamp.astimezone(utc)
    
    day_of_week = timestamp.strftime('%A')  # Ex: 'Monday'
    hour = timestamp.hour

    for session, hours in sessions.items():
        if hours['start'] <= hour < hours['end']:
            return day_of_week, session
    return day_of_week, 'Unknown'

def compute_trade_metrics(trade_list):
    """
    Calcule les métriques pour une liste de trades.
    Retourne un dictionnaire avec les métriques.
    """
    if not trade_list:
        return {
            'total_trades': 0,
            'wins': 0,
            'losses': 0,
            'win_rate': 0,
            'total_pnl_fixed': 0,
            'total_pnl_compound': 0,
            'total_pnl_daily': 0
        }
    
    total_trades = len(trade_list)
    wins = sum(1 for trade in trade_list if trade['result'] == 'win')
    losses = total_trades - wins
    win_rate = (wins / total_trades) * 100
    total_pnl_fixed = sum(trade['pnl_fixed'] for trade in trade_list)
    total_pnl_compound = sum(trade['pnl_compound'] for trade in trade_list)
    total_pnl_daily = sum(trade['pnl_daily'] for trade in trade_list)
    
    return {
        'total_trades': total_trades,
        'wins': wins,
        'losses': losses,
        'win_rate': win_rate,
        'total_pnl_fixed': total_pnl_fixed,
        'total_pnl_compound': total_pnl_compound,
        'total_pnl_daily': total_pnl_daily
    }

def save_trades_to_csv(trades, filename):
    """
    Sauvegarde les détails des trades dans un fichier CSV.
    Ajoute SL, TP, entry_price et exit_price uniquement pour le fichier CSV.
    """
    headers = [
        'pair', 'entry_time', 'exit_time', 'direction',
        'entry_price', 'exit_price',  # Colonnes pour les prix
        'sl', 'tp',  # Colonnes pour SL et TP
        'pnl_fixed', 'pnl_compound', 'pnl_daily',
        'result'
    ]

    # Vérifie si le fichier existe déjà
    file_exists = os.path.isfile(filename)

    with open(filename, mode='a', newline='') as file:
        writer = csv.DictWriter(file, fieldnames=headers)
        if not file_exists:
            writer.writeheader()  # Écrit les en-têtes si le fichier est nouveau

        for trade in trades:
            # Ajout des informations SL, TP, entry_price, exit_price si elles ne sont pas déjà présentes
            writer.writerow({
                'pair': trade.get('pair', ''),
                'entry_time': trade.get('entry_time', ''),
                'exit_time': trade.get('exit_time', ''),
                'direction': trade.get('direction', ''),
                'entry_price': trade.get('entry_price', ''),
                'exit_price': trade.get('exit_price', ''),
                'sl': trade.get('sl', ''),  # Niveau SL
                'tp': trade.get('tp', ''),  # Niveau TP
                'pnl_fixed': trade.get('pnl_fixed', ''),
                'pnl_compound': trade.get('pnl_compound', ''),
                'pnl_daily': trade.get('pnl_daily', ''),
                'result': trade.get('result', '')
            })


# ============================================================
# 3) FONCTIONS D'EXÉCUTION DES TRADES
# ============================================================

def execution(b_point, c, direction, data, p_fractal, psl, day_balance_start, opposite_inv, entry_time, entry_price):
    """
    Fonction d'exécution d'un trade (SELL ou BUY).
    Retourne :
      - un tuple ( [SL_line, PE_line, TP_line], trade_details )
      - ou "invalidation" si invalidé
    """
    print(f"\n[DEBUG] Appel de la fonction execution()")
    print(f"[DEBUG]   b_point={b_point}, c={c}, direction={direction}, taille data={len(data)}")

    c_count = 0
    countcandle = 0

    # Approche #3 : on fige la balance journalière
    Rdaily = risk_percentage * day_balance_start

    if direction == "BUY":
        print("[DEBUG]  -> direction = BUY")
        for idx, row in data.iterrows():
            if countcandle >= 2:
                if (row['low'] < data.iloc[data.index.get_loc(idx)-1]["low"] and
                    data.iloc[data.index.get_loc(idx)-1]['low'] < data.iloc[data.index.get_loc(idx)-2]['low']):
                    p_fractal = data.iloc[data.index.get_loc(idx)-1]['low']

            c_count += 1

            if row["low"] < c and c_count == 1:
                if row["high"] > opposite_inv:
                    return "invalidation"

            if row["low"] < c and c_count > 1:
                return "invalidation"

            # Condition d'entrée
            if row["high"] > b_point:
                print(f"[DEBUG]  -> row['high']={row['high']} > b_point={b_point} => Trade BUY potentiel")

                if psl < row["low"]:
                    sl = psl
                else:
                    sl = p_fractal

                tp = b_point + (b_point - sl)*riskratio
                print(f"[DEBUG]  -> SL={sl}, TP={tp}")

                # Boucle pour SL/TP
                for idx2, row2 in data.loc[idx:].iterrows():
                    if row2['low'] < sl:
                        print(f"[DEBUG]  -> SL touché (BUY) à l'index {idx2}")
                        # Perte => -1R
                        pnl_fixed, pnl_compound, _, Rfix, Rcomp = calcul_pnl_for_3_modes(-1)
                        pnl_daily = Rdaily * (-1)

                        # Calcul des frais basés sur la taille de la position
                        pnl_fixed     -= 2 * fees * Rfix
                        pnl_compound  -= 2 * fees * Rcomp
                        pnl_daily     -= 2 * fees * Rdaily

                        trade_details = {
                            'pair': 'BTC_USDT',  # Assurez-vous de changer ceci si nécessaire
                            'entry_time': entry_time,
                            'exit_time': idx2,
                            'direction': direction,
                            'entry_price': entry_price,
                            'exit_price': sl,
                            'pnl_fixed': pnl_fixed,
                            'pnl_compound': pnl_compound,
                            'pnl_daily': pnl_daily,
                            'result': 'loss'
                        }

                        return (
                            [[(idx, sl), (idx2, sl)],
                             [(idx, b_point), (idx2, b_point)],
                             [(idx, tp), (idx2, tp)]],
                            trade_details
                        )

                    if row2["high"] > tp:
                        print(f"[DEBUG]  -> TP touché (BUY) à l'index {idx2}")
                        # Gain => +riskratio R (typiquement +2R)
                        pnl_fixed, pnl_compound, _, Rfix, Rcomp = calcul_pnl_for_3_modes(+riskratio)
                        pnl_daily = Rdaily * (+riskratio)

                        # Calcul des frais basés sur la taille de la position
                        pnl_fixed     -= 2 * fees * Rfix
                        pnl_compound  -= 2 * fees * Rcomp
                        pnl_daily     -= 2 * fees * Rdaily

                        trade_details = {
                            'pair': 'BTC_USDT',  # Assurez-vous de changer ceci si nécessaire
                            'entry_time': entry_time,
                            'exit_time': idx2,
                            'direction': direction,
                            'entry_price': entry_price,
                            'exit_price': tp,
                            'pnl_fixed': pnl_fixed,
                            'pnl_compound': pnl_compound,
                            'pnl_daily': pnl_daily,
                            'result': 'win'
                        }

                        return (
                            [[(idx, sl), (idx2, sl)],
                             [(idx, b_point), (idx2, b_point)],
                             [(idx, tp), (idx2, tp)]],
                            trade_details
                        )

            psl = row['low']
            countcandle += 1

    elif direction == "SELL":
        print("[DEBUG]  -> direction = SELL")
        for idx, row in data.iterrows():
            if countcandle >= 2:
                if (row['high'] > data.iloc[data.index.get_loc(idx)-1]["high"] and
                    data.iloc[data.index.get_loc(idx)-1]['high'] > data.iloc[data.index.get_loc(idx)-2]['high']):
                    p_fractal = data.iloc[data.index.get_loc(idx)-1]['high']

            c_count += 1

            if row["high"] > c and c_count == 1:
                if row["low"] < opposite_inv:
                    return "invalidation"

            if row["high"] > c and c_count > 1:
                return "invalidation"

            # Condition d'entrée
            if row["low"] < b_point:
                print(f"[DEBUG]  -> row['low']={row['low']} < b_point={b_point} => Trade SELL potentiel")

                if psl > row["high"]:
                    sl = psl
                else:
                    sl = p_fractal

                tp = b_point - (sl - b_point)*riskratio
                print(f"[DEBUG]  -> SL={sl}, TP={tp}")

                for idx2, row2 in data.loc[idx:].iterrows():
                    if row2['high'] > sl:
                        print(f"[DEBUG]  -> SL touché (SELL) à l'index {idx2}")
                        # Perte => -1R
                        pnl_fixed, pnl_compound, _, Rfix, Rcomp = calcul_pnl_for_3_modes(-1)
                        pnl_daily = Rdaily * (-1)

                        # Calcul des frais basés sur la taille de la position
                        pnl_fixed     -= 2 * fees * Rfix
                        pnl_compound  -= 2 * fees * Rcomp
                        pnl_daily     -= 2 * fees * Rdaily

                        trade_details = {
                            'pair': 'BTC_USDT',  # Assurez-vous de changer ceci si nécessaire
                            'entry_time': entry_time,
                            'exit_time': idx2,
                            'direction': direction,
                            'entry_price': entry_price,
                            'exit_price': sl,
                            'pnl_fixed': pnl_fixed,
                            'pnl_compound': pnl_compound,
                            'pnl_daily': pnl_daily,
                            'result': 'loss'
                        }

                        return (
                            [[(idx, sl), (idx2, sl)],
                             [(idx, b_point), (idx2, b_point)],
                             [(idx, tp), (idx2, tp)]],
                            trade_details
                        )

                    if row2["low"] < tp:
                        print(f"[DEBUG]  -> TP touché (SELL) à l'index {idx2}")
                        # Gain => +riskratio R (typiquement +2R)
                        pnl_fixed, pnl_compound, _, Rfix, Rcomp = calcul_pnl_for_3_modes(+riskratio)
                        pnl_daily = Rdaily * (+riskratio)

                        # Calcul des frais basés sur la taille de la position
                        pnl_fixed     -= 2 * fees * Rfix
                        pnl_compound  -= 2 * fees * Rcomp
                        pnl_daily     -= 2 * fees * Rdaily

                        trade_details = {
                            'pair': 'BTC_USDT',  # Assurez-vous de changer ceci si nécessaire
                            'entry_time': entry_time,
                            'exit_time': idx2,
                            'direction': direction,
                            'entry_price': entry_price,
                            'exit_price': tp,
                            'pnl_fixed': pnl_fixed,
                            'pnl_compound': pnl_compound,
                            'pnl_daily': pnl_daily,
                            'result': 'win'
                        }

                        return (
                            [[(idx, sl), (idx2, sl)],
                             [(idx, b_point), (idx2, b_point)],
                             [(idx, tp), (idx2, tp)]],
                            trade_details
                        )
            psl = row['high']
            countcandle += 1

    print("[DEBUG]  -> Aucune condition de sortie => invalidation")
    return "invalidation"

# ============================================================
# 3) SCRIPT PRINCIPAL (Lecture CSV, fractals, setup trades)
# ============================================================

print("[DEBUG] Lecture du fichier CSV et génération du dataset ...")
h4_rows = module.tools.get_dataset("data/ohlcv_paradex_BTC-USD-PERP_1m_360d.csv")
print("[DEBUG] h4_rows (dataset) récupéré :", len(h4_rows))

fractals = module.structure.fractality(h4_rows)
print("[DEBUG] fractals générés :", len(fractals))

df = pd.read_csv("data/ohlcv_paradex_BTC-USD-PERP_1m_360d.csv", index_col=0, parse_dates=True)
print("[DEBUG] df (pandas DataFrame) chargé :", df.shape)

print("=== APERÇU DES DONNÉES ===")
print("h4_rows:", h4_rows[:5] if len(h4_rows) > 5 else h4_rows)
print("fractals:", fractals[:5] if len(fractals) > 5 else fractals)
print("df head:")
print(df.head())

print("\n[DEBUG] Début de la boucle de détection fractals ...")

last_hh = None
last_ll = None

for a in fractals:
    print(f"\n[DEBUG] Traitement du fractal : {a}")
    count = 0
    fractal_time = pd.to_datetime(a[2])

    # SELL
    if a[0] in ["HH", "LH"]:
        print(f"[DEBUG]  -> fractal de type {a[0]} => SELL possible")
        if last_ll is not None:
            b = [df.index[-1], float('inf')]
            for i, row in df.iloc[df.index.get_loc(last_ll[2]):].iterrows():
                if i > fractal_time:
                    count += 1
                    if count >= maximum_candle_between_a_and_c:
                        print("[DEBUG]  -> Trop de bougies => break")
                        break
                    if row['low'] < float(last_ll[1]):
                        break
                    if row['low'] < float(b[1]):
                        b = [i, row['low']]

                    if (row['high'] > float(a[1]) and
                        row['close'] < float(a[1]) and
                        row['open'] < float(a[1])):

                        if i == b[0]:
                            break

                        print("[DEBUG]  -> Condition SELL => execution()")
                        day_balance = get_daily_balance(i)

                        ret_code = execution(
                            b[1], row['high'], "SELL",
                            df.iloc[df.index.get_loc(i)+1:],
                            row['high'], row['high'],
                            day_balance,
                            row["low"],
                            entry_time=i,
                            entry_price=b[1]
                        )

                        if ret_code == "invalidation":
                            invalidationabc.append([(fractal_time, float(a[1])), (i, float(a[1]))])
                        else:
                            (lines, trade_details) = ret_code
                            if i == p_point:
                                sl_abc.pop()
                                tp_abc.pop()
                                pe_abc.pop()
                                capital_list_fixed.pop()
                                capital_list_compound.pop()
                                capital_list_daily.pop()

                            sl_abc.append(lines[0])
                            pe_abc.append(lines[1])
                            tp_abc.append(lines[2])

                            pnl_fixed, pnl_compound, pnl_daily = trade_details['pnl_fixed'], trade_details['pnl_compound'], trade_details['pnl_daily']
                            capital_list_fixed.append(capital_list_fixed[-1] + pnl_fixed)
                            capital_list_compound.append(capital_list_compound[-1] + pnl_compound)
                            capital_list_daily.append(capital_list_daily[-1] + pnl_daily)

                            valid_abc.append([(fractal_time, float(a[1])), (i, float(a[1]))])

                            # Enregistrement du trade
                            trades.append(trade_details)

                        p_point = i
                        break

                    if row['high'] > float(a[1]):
                        break
        last_hh = a

    # BUY
    elif a[0] in ["LL", "HL"]:
        print(f"[DEBUG]  -> fractal de type {a[0]} => BUY possible")
        if last_hh is not None:
            b = [df.index[0], 0]
            for i, row in df.iloc[df.index.get_loc(last_hh[2]):].iterrows():
                if i > fractal_time:
                    count += 1
                    if count >= maximum_candle_between_a_and_c:
                        break
                    if row['high'] > float(last_hh[1]):
                        break
                    if row['high'] > float(b[1]):
                        b = [i, row['high']]

                    if (row['low'] < float(a[1]) and
                        row['close'] > float(a[1]) and
                        row['open'] > float(a[1])):

                        if i == b[0]:
                            break

                        print("[DEBUG]  -> Condition BUY => execution()")
                        day_balance = get_daily_balance(i)

                        ret_code = execution(
                            b[1], row['low'], "BUY",
                            df.iloc[df.index.get_loc(i)+1:],
                            row['low'], row['low'],
                            day_balance,
                            row["high"],
                            entry_time=i,
                            entry_price=b[1]
                        )

                        if ret_code == "invalidation":
                            invalidationabc.append([(fractal_time, float(a[1])), (i, float(a[1]))])
                        else:
                            (lines, trade_details) = ret_code
                            if i == p_point:
                                sl_abc.pop()
                                tp_abc.pop()
                                pe_abc.pop()
                                capital_list_fixed.pop()
                                capital_list_compound.pop()
                                capital_list_daily.pop()

                            sl_abc.append(lines[0])
                            pe_abc.append(lines[1])
                            tp_abc.append(lines[2])

                            pnl_fixed, pnl_compound, pnl_daily = trade_details['pnl_fixed'], trade_details['pnl_compound'], trade_details['pnl_daily']
                            capital_list_fixed.append(capital_list_fixed[-1] + pnl_fixed)
                            capital_list_compound.append(capital_list_compound[-1] + pnl_compound)
                            capital_list_daily.append(capital_list_daily[-1] + pnl_daily)

                            valid_abc.append([(fractal_time, float(a[1])), (i, float(a[1]))])

                            # Enregistrement du trade
                            trades.append(trade_details)

                        p_point = i
                        break

                    if row['low'] < float(a[1]):
                        break
        last_ll = a

print("\n[DEBUG] Fin de la boucle fractals.")
print(" - invalidationabc:", invalidationabc)
print(" - valid_abc:", valid_abc)
print(" - sl_abc:", sl_abc)
print(" - pe_abc:", pe_abc)
print(" - tp_abc:", tp_abc)
print(" - capital_list_fixed:", capital_list_fixed)
print(" - capital_list_compound:", capital_list_compound)
print(" - capital_list_daily:", capital_list_daily)

# ============================================================
# 4) AFFICHAGE DES FRACTALS + TRACES SUR MPFINANCE
# ============================================================

marker_up = [np.nan] * len(df)
marker_down = [np.nan] * len(df)

for f in fractals:
    fractal_type = f[0]
    fractal_price = float(f[1])
    fractal_time = pd.to_datetime(f[2])
    if fractal_time in df.index:
        idx = df.index.get_loc(fractal_time)
        if fractal_type in ['HH', 'LH']:
            marker_up[idx] = fractal_price * 1.0001
        elif fractal_type in ['LL', 'HL']:
            marker_down[idx] = fractal_price * 0.9999

ap_up = mpf.make_addplot(marker_up, type='scatter', marker='^', color='r', markersize=100)
ap_down = mpf.make_addplot(marker_down, type='scatter', marker='v', color='g', markersize=100)

def convert_traces_to_alines(trace_list):
    lines = []
    for seg in trace_list:
        timeA = seg[0][0]
        priceA = seg[0][1]
        timeB = seg[1][0]
        priceB = seg[1][1]

        if timeA not in df.index:
            print("[ALERT] t1 n'est pas dans df.index =>", timeA)
        if timeB not in df.index:
            print("[ALERT] t2 n'est pas dans df.index =>", timeB)

        timeA_str = timeA.strftime('%Y-%m-%d %H:%M:%S')
        timeB_str = timeB.strftime('%Y-%m-%d %H:%M:%S')

        lines.append([(timeA_str, priceA), (timeB_str, priceB)])
    return lines

inva_lines = convert_traces_to_alines(invalidationabc)
val_lines  = convert_traces_to_alines(valid_abc)
sl_lines   = convert_traces_to_alines(sl_abc)
pe_lines   = convert_traces_to_alines(pe_abc)
tp_lines   = convert_traces_to_alines(tp_abc)

lines_merged = []
colors_merged = []

for seg in val_lines:
    lines_merged.append(seg)
    colors_merged.append('black')
for seg in inva_lines:
    lines_merged.append(seg)
    colors_merged.append('orange')
for seg in sl_lines:
    lines_merged.append(seg)
    colors_merged.append('red')
for seg in pe_lines:
    lines_merged.append(seg)
    colors_merged.append('blue')
for seg in tp_lines:
    lines_merged.append(seg)
    colors_merged.append('green')

alines_dict = dict(
    alines=lines_merged,
    colors=colors_merged,
    linewidths=1,
    alpha=0.35
)

print("[DEBUG] Affichage du graphique principal (MPLFinance) ...")
mpf.plot(
    df,
    type='candle',
    style='yahoo',
    addplot=[ap_up, ap_down],
    alines=alines_dict,  
    title='BTC-USD-PERP - Fractals (SL / PE / TP / Invalid / Valid)',
    volume=True
)

# ============================================================
# 5) ANALYSE PAR JOUR DE LA SEMAINE ET PAR SESSION
# ============================================================

# Catégorisation des trades par jour et par session
trades_by_day = collections.defaultdict(list)
trades_by_session = collections.defaultdict(list)

for trade in trades:
    entry_time = trade['entry_time']
    # Si l'index de df est timezone-aware, sinon assume UTC
    if isinstance(entry_time, pd.Timestamp):
        if entry_time.tzinfo is None:
            entry_time = utc.localize(entry_time.to_pydatetime())
        else:
            entry_time = entry_time.tz_convert(utc)
    else:
        # Convertir en Timestamp si nécessaire
        entry_time = pd.to_datetime(entry_time).tz_localize('UTC')

    day, session = categorize_trade(entry_time)
    trades_by_day[day].append(trade)
    trades_by_session[session].append(trade)

# Calcul des métriques
metrics_by_day = {day: compute_trade_metrics(trades) for day, trades in trades_by_day.items()}
metrics_by_session = {session: compute_trade_metrics(trades) for session, trades in trades_by_session.items()}

# ============================================================
# 6) VISUALISATION DES MÉTRIQUES PAR CATÉGORIE
# ============================================================

# a. Visualisation par Jour de la Semaine
days_order = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday']
pnl_by_day_fixed = [metrics_by_day.get(day, {}).get('total_pnl_fixed', 0) for day in days_order]
pnl_by_day_compound = [metrics_by_day.get(day, {}).get('total_pnl_compound', 0) for day in days_order]
pnl_by_day_daily = [metrics_by_day.get(day, {}).get('total_pnl_daily', 0) for day in days_order]

x = np.arange(len(days_order))  # the label locations
width = 0.25  # the width of the bars

plt.figure(figsize=(12, 7))
plt.bar(x - width, pnl_by_day_fixed, width, label='Risque Fixe')
plt.bar(x, pnl_by_day_compound, width, label='Risque Composé')
plt.bar(x + width, pnl_by_day_daily, width, label='Risque Quotidien')

plt.xlabel('Jour de la Semaine')
plt.ylabel('PnL Total')
plt.title('PnL Total par Jour de la Semaine et Approche de Risque')
plt.xticks(x, days_order)
plt.legend()
plt.grid(axis='y')
plt.tight_layout()
plt.show()

# b. Visualisation par Session de Trading
sessions_order = ['Asie', 'Londres', 'New York', 'Unknown']
pnl_by_session_fixed = [metrics_by_session.get(session, {}).get('total_pnl_fixed', 0) for session in sessions_order]
pnl_by_session_compound = [metrics_by_session.get(session, {}).get('total_pnl_compound', 0) for session in sessions_order]
pnl_by_session_daily = [metrics_by_session.get(session, {}).get('total_pnl_daily', 0) for session in sessions_order]

x = np.arange(len(sessions_order))  # the label locations

plt.figure(figsize=(12, 7))
plt.bar(x - width, pnl_by_session_fixed, width, label='Risque Fixe')
plt.bar(x, pnl_by_session_compound, width, label='Risque Composé')
plt.bar(x + width, pnl_by_session_daily, width, label='Risque Quotidien')

plt.xlabel('Session de Trading')
plt.ylabel('PnL Total')
plt.title('PnL Total par Session de Trading et Approche de Risque')
plt.xticks(x, sessions_order)
plt.legend()
plt.grid(axis='y')
plt.tight_layout()
plt.show()

# c. Affichage des Métriques
print("\n=== Métriques par Jour de la Semaine ===")
for day in days_order:
    metrics = metrics_by_day.get(day)
    if metrics:
        print(f"{day}: {metrics}")

print("\n=== Métriques par Session de Trading ===")
for session in sessions_order:
    metrics = metrics_by_session.get(session)
    if metrics:
        print(f"{session}: {metrics}")

# ============================================================
# 7) AFFICHAGE 3 GRAPHIQUES SÉPARÉS
# ============================================================

# 1) Risque fixe
plot_equity_curve_with_metrics(capital_list_fixed, "Fixed Risk Approach")

# 2) Risque composé
plot_equity_curve_with_metrics(capital_list_compound, "Compounding Risk Approach")

# 3) Risque avec balance quotidienne
plot_equity_curve_with_metrics(capital_list_daily, "Daily Risk Approach")

# ============================================================
# 8) SAUVEGARDE DES TRADES DANS LE FICHIER CSV
# ============================================================

# Sauvegarder les trades dans le fichier CSV
save_trades_to_csv(trades, trades_filename)
print(f"[INFO] Trades sauvegardés dans {trades_filename}")

print("[DEBUG] Fin du script.")
