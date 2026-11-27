# SsalimutoProfits EA – Setup Guide (for beginners)

Made by Ssali Muto. **No bot can promise no losses.** Only use money you can afford to lose.

This guide shows you how to run the robot (called an "EA", Expert Advisor) on MetaTrader 5 (MT5), all day and all night.

---

## What the robot does

- It looks at **daily candles (D1)** once a day.
- It trades only **GBPUSD, USDCHF and AUDUSD**. These are the only pairs that passed our tests. EURGBP is switched off.
- It mostly uses **mean reversion**: when price is in an up-trend but drops a lot for a short time, it buys and waits for the price to come back. (The opposite for down-trends.) AUDUSD uses "auto": it follows the trend when the trend is strong, and uses mean reversion when it is not.
- Lot size is **never more than 0.01**.
- Every trade has a **stop loss** (limits the loss) and a **take profit** (closes the trade in profit).
- It will **skip** a trade if the stop loss could lose more than **3%** of your balance.
- It stops for the day after **3 trades** or after a **3% loss** in the day.
- If your account falls **15%** from its highest point, it closes its trades and **stops** completely.
- Only **one trade per pair** at a time. No martingale (doubling lots after a loss). No grid.

By default the robot is in **signal-only mode** (`InpLive = false`). It only writes what it *would* do. It does not trade. Keep it like this for several weeks.

---

## Step 1 – Get a computer that is always on

The robot only works while MT5 is open and connected. Your phone cannot run an EA. You need one of these:

### Option A (easiest): MQL5 built-in VPS
This is a small server run by MetaQuotes (the company that makes MT5). It costs about **$10–15 per month**, paid by bank card.

1. First do Steps 2 to 5 on any Windows computer (a friend's, an internet café, etc.).
2. In MT5, go to **Tools > Options > VPS**.
3. Choose a plan and pay with your card.
4. Right-click your account in the **Navigator** window and choose **Register a Virtual Server**.
5. Choose **"Migrate experts and indicators"**. Your chart with the robot is copied to the VPS.
6. Now you can switch off the computer. The robot keeps running on the VPS.
7. Each time you change a setting, migrate again (right-click the account > Register a Virtual Server > Migrate).

Note: on the MQL5 VPS you cannot see the chart. Read the robot's messages in **Toolbox > VPS > Journal** in your MT5.

### Option B: Rent a Windows VPS
A Windows VPS is a computer in a data centre that you control from your phone or PC.

1. Rent a small **Windows** VPS (1–2 GB RAM is enough). Many companies sell them for about **$10–20 per month**, paid by card.
2. They send you an address (IP), a username and a password.
3. Connect with **Remote Desktop**: on Windows open "Remote Desktop Connection"; on Android/iPhone install the "Microsoft Remote Desktop" (Windows App) app.
4. Inside the VPS, do Steps 2 to 5 below.
5. When you leave, just close the Remote Desktop window. **Do not shut down the VPS.**

---

## Step 2 – Install MT5

1. On the Windows computer or VPS, download **MetaTrader 5** from the official site (metatrader5.com) or from your broker.
2. Install it with the normal settings.

## Step 3 – Log in to Pocket Option's MT5 server

1. Open MT5. Go to **File > Login to Trade Account**.
2. Login: your Pocket Option MT5 account number.
3. Password: your MT5 trading password (not your Pocket Option website password, unless they are the same).
4. Server: type **PoTrade-MT5** and choose it from the list.
5. Click OK. At the bottom right you should see a connection speed (green bars), not "No connection".

Tip: start with a **demo** account if you can.

## Step 4 – Put the EA in the Experts folder

1. In MT5, go to **File > Open Data Folder**.
2. Open **MQL5**, then **Experts**.
3. Copy **SsalimutoProfits.mq5** into this folder.
4. Back in MT5, press **F4** (opens MetaEditor). Find the file on the left under **Experts**, open it, and press **F7** (Compile).
5. At the bottom it must say **0 errors**. If you see errors, copy them and ask for help.
6. Close MetaEditor. In MT5, in the **Navigator** window, right-click **Expert Advisors** and click **Refresh**.

## Step 5 – Attach the EA to the chart

1. Open a **GBPUSD** chart (File > New Chart > GBPUSD).
2. Set it to **D1** (click "D1" on the top bar).
3. Make sure GBPUSD, USDCHF and AUDUSD are in **Market Watch** (right-click Market Watch > Symbols). The robot also tries to add them itself.
4. Drag **SsalimutoProfits** from Navigator onto the chart.
5. In the window that opens:
   - **Common** tab: tick **Allow Algo Trading**.
   - **Inputs** tab: leave **InpLive = false** and **InpAcceptRisk = false**.
   - If your broker's pair names have an ending (for example `GBPUSD.m`), put that ending (`.m`) in **InpSymbolSuffix**. Look at the names in Market Watch.
6. Click OK.
7. On the top toolbar, click the **Algo Trading** button so it is **green**.

You only need **one** chart. The robot checks all three pairs from that one chart.

## Step 6 – Check that it works

- Look at **Toolbox > Experts** (press Ctrl+T to open the Toolbox).
- You should see: `SsalimutoProfits started in SIGNAL-ONLY (no trades) mode`.
- When a signal comes, you will see a line like:
  `[signal only] would BUY GBPUSD (mr) 0.01 lot ... SL ... TP ...`
- Signals are rare. This is a daily robot. Many days nothing happens. Some weeks nothing happens.

## Step 7 – Keep InpLive = false for weeks first

- Leave it in signal-only mode for **at least 4–8 weeks**.
- Write down each signal and check later: would it have won or lost?
- Only if you are happy, change to live:
  1. Right-click the chart > **Expert List** > select the robot > **Properties** > **Inputs**.
  2. Set **InpLive = true** and **InpAcceptRisk = true**.
  3. Click OK. The Experts tab should now say **LIVE**.
  4. If you use the MQL5 VPS, migrate again (Step 1, Option A, point 7).

---

## Emergency stop

Any of these stops new trades:

- Click the **Algo Trading** button so it is **red**.
- Remove the robot from the chart (right-click the chart > Expert List > Remove).
- Create an empty file called **SsalimutoProfits_STOP.txt** in **File > Open Data Folder > MQL5 > Files**.

Open trades still have their stop loss and take profit at the broker. You can also close them yourself in the **Trade** tab.

If the 15% drawdown stop fired, the robot stays stopped. To restart it, set **InpResetHalt = true**, click OK, then set it back to **false**.

## Settings you can change

| Setting | Default | Meaning |
|---|---|---|
| InpLive | false | false = only print signals. true = real trades (also needs InpAcceptRisk). |
| InpAcceptRisk | false | Must be true for real trades. |
| MagicNumber | 20261127 | ID number for this robot's trades. Change only if you run two copies. |
| InpTradeGBPUSD / USDCHF / AUDUSD | true | Turn a pair on or off. |
| InpTradeEURGBP | false | Weakest pair in tests. Keep off. |
| InpSymbolSuffix | (empty) | Ending of pair names at your broker, e.g. `.m`. |
| InpLots | 0.01 | Lot size. It can never go above 0.01. |
| InpMaxRiskPct | 3 | Skip a trade if its stop could lose more than this % of balance. |
| InpDailyLossPct | 3 | No new trades today after this % loss. |
| InpMaxDrawdownPct | 15 | Close the robot's trades and stop at this % fall from the peak. |
| InpMaxTradesPerDay | 3 | Max new trades per day. |
| InpMaxSpreadPips | 5 | Wait if the spread is wider than this. |

## Important

- Past test results do **not** promise future profit. Over about 3 years of test data, these pairs made only a few % each, with about 23–31 trades each.
- With a very small balance, even 0.01 lot can be more than 3% risk. Then the robot will skip trades. That is the safety rule working.
- Never give anyone your MT5 password. Never pay anyone who promises "guaranteed profit".
