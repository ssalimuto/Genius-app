//+------------------------------------------------------------------+
//|                                            SsalimutoProfits.mq5  |
//|                                                                  |
//|  Made by Ssali Muto. No bot can promise no losses.               |
//|                                                                  |
//|  Daily (D1) strategy, ported from safe_mt5_bot.py v2:            |
//|   - Mean reversion in the EMA200 trend: buy when price is above  |
//|     a rising EMA200 and RSI(2) is very low OR the close is under |
//|     the lower Bollinger band (20, 2). Sell is the mirror image.  |
//|     Exit when the close crosses back over the 5-bar average,     |
//|     after a time limit, or at the stop loss / take profit.       |
//|   - "Auto" (AUDUSD only): ADX >= 25 -> trend breakout rules,     |
//|     ADX < 25 -> mean reversion rules.                            |
//|                                                                  |
//|  Pairs and settings = only the ones that PASSED walk-forward     |
//|  testing on daily data (settings picked on the old 70% of data,  |
//|  judged on the unseen newest 30%):                               |
//|     GBPUSD  meanrev  RSI<10, SL 2.5 ATR, TP 3 ATR, max 24 bars   |
//|     USDCHF  meanrev  RSI<5,  SL 2.5 ATR, TP 3 ATR, max 12 bars   |
//|     AUDUSD  auto     ADX 25, trend SL 2 ATR / MR SL 2.5 ATR,     |
//|                      TP 3 ATR, breakout 20, max 24 bars          |
//|     EURGBP  meanrev  RSI<10, SL 1.5 ATR, TP 3 ATR, max 12 bars   |
//|             (weakest pass: OFF by default)                       |
//|  Passing a test does NOT mean the pair will make money later.    |
//|                                                                  |
//|  Safety guards:                                                  |
//|   - InpLive=false (default): only prints signals, never trades.  |
//|   - Real orders need InpLive=true AND InpAcceptRisk=true AND     |
//|     Algo Trading switched on.                                    |
//|   - Lot size is at most 0.01. Every order has a stop loss and a  |
//|     take profit.                                                 |
//|   - Trade skipped if the stop would risk more than 3% of balance.|
//|   - Max trades per day, daily loss stop, max drawdown stop from  |
//|     the equity peak (closes this EA's positions and halts).      |
//|   - One position per symbol. No martingale. No grid.             |
//|   - Kill switch file: create MQL5\Files\SsalimutoProfits_STOP.txt|
//|     and the EA stops opening trades.                             |
//+------------------------------------------------------------------+
#property copyright "Made by Ssali Muto. No bot can promise no losses."
#property version   "1.00"
#property description "D1 mean reversion (EMA200 + RSI2 + Bollinger) on pairs that passed walk-forward."
#property description "InpLive=false = signals only. Max 0.01 lot. SL+TP on every order. No martingale, no grid."
#property description "Made by Ssali Muto. No bot can promise no losses."

#include <Trade\Trade.mqh>

//--- inputs ----------------------------------------------------------
input group "Safety switches"
input bool   InpLive               = false;  // Live trading (false = only print signals)
input bool   InpAcceptRisk         = false;  // I accept I can lose money (needed for live)
input long   MagicNumber           = 20261127; // Magic number (ID of this EA's trades)

input group "Pairs (only ones that passed testing)"
input bool   InpTradeGBPUSD        = true;   // GBPUSD (mean reversion)
input bool   InpTradeUSDCHF        = true;   // USDCHF (mean reversion)
input bool   InpTradeAUDUSD        = true;   // AUDUSD (auto: trend or mean reversion by ADX)
input bool   InpTradeEURGBP        = false;  // EURGBP (weakest pass, off by default)
input string InpSymbolSuffix       = "";     // Broker symbol suffix, e.g. ".m" (empty if none)

input group "Risk"
input double InpLots               = 0.01;   // Lot size (hard capped at 0.01)
input double InpMaxRiskPct         = 3.0;    // Skip trade if stop risk > this % of balance
input double InpDailyLossPct       = 3.0;    // Stop new trades after this % loss today
input double InpMaxDrawdownPct     = 15.0;   // Close EA trades and halt at this % drawdown from peak
input int    InpMaxTradesPerDay    = 3;      // Max new trades per day (all pairs together)
input double InpMaxSpreadPips      = 5.0;    // Wait if spread is wider than this (pips)
input int    InpMaxEntryDelayHours = 6;      // Do not enter if the new day bar is older than this
input bool   InpResetHalt          = false;  // Set true once to clear a drawdown halt (then set false)

input group "Other"
input int    InpSlippagePoints     = 30;     // Max slippage (points)
input int    InpTimerSeconds       = 30;     // How often to check (seconds)

//--- constants -------------------------------------------------------
#define SP_TF            PERIOD_D1
#define MAX_LOT       0.01
#define WARMUP_BARS   210
#define ATR_BARS      300
#define KIND_MR       1
#define KIND_TREND    2
#define SP_MODE_MEANREV  0
#define SP_MODE_AUTO     1
#define STOP_FILE     "SsalimutoProfits_STOP.txt"

//--- per pair settings (from wf_results.json, all tf = 1d, pass = true)
struct PairCfg
  {
   string            base;        // e.g. "GBPUSD"
   string            sym;         // broker symbol name
   bool              enabled;
   int               mode;        // SP_MODE_MEANREV or SP_MODE_AUTO
   int               ema;
   int               atr;
   double            bb_k;
   int               rsi_lo;
   double            sl_atr;      // meanrev stop (meanrev) / trend stop (auto)
   double            mr_sl_atr;   // meanrev stop inside auto
   double            tp_atr;
   int               max_bars;
   double            adx_th;
   int               breakout;
   //--- runtime
   bool              ready;
   int               hEma;
   int               hSma5;
   int               hBands;
   int               hRsi;
   int               hAdx;
   datetime          lastDone;    // open time of the last CLOSED bar already handled
  };

PairCfg  g_pairs[];
CTrade   g_trade;
bool     g_live          = false;
int      g_dryTradesDay  = 0;     // signals "taken" in dry run today
string   g_dryDay        = "";
string   g_gv;                    // global variable prefix

//+------------------------------------------------------------------+
void AddPair(const string base,const bool enabled,const int mode,const int rsi_lo,
             const double sl_atr,const double mr_sl_atr,const double tp_atr,const int max_bars,
             const double adx_th,const int breakout)
  {
   int n=ArraySize(g_pairs);
   ArrayResize(g_pairs,n+1);
   g_pairs[n].base=base;
   g_pairs[n].sym=base+InpSymbolSuffix;
   g_pairs[n].enabled=enabled;
   g_pairs[n].mode=mode;
   g_pairs[n].ema=200;
   g_pairs[n].atr=14;
   g_pairs[n].bb_k=2.0;
   g_pairs[n].rsi_lo=rsi_lo;
   g_pairs[n].sl_atr=sl_atr;
   g_pairs[n].mr_sl_atr=mr_sl_atr;
   g_pairs[n].tp_atr=tp_atr;
   g_pairs[n].max_bars=max_bars;
   g_pairs[n].adx_th=adx_th;
   g_pairs[n].breakout=breakout;
   g_pairs[n].ready=false;
   g_pairs[n].hEma=INVALID_HANDLE;
   g_pairs[n].hSma5=INVALID_HANDLE;
   g_pairs[n].hBands=INVALID_HANDLE;
   g_pairs[n].hRsi=INVALID_HANDLE;
   g_pairs[n].hAdx=INVALID_HANDLE;
   g_pairs[n].lastDone=0;
  }

//+------------------------------------------------------------------+
int OnInit()
  {
   g_gv=StringFormat("SP_%I64d_",MagicNumber);

   if(InpLots<=0.0)
     {
      Print("InpLots must be above 0.");
      return(INIT_PARAMETERS_INCORRECT);
     }
   if(InpLots>MAX_LOT)
      Print("InpLots ",DoubleToString(InpLots,2)," is above the 0.01 cap. Using 0.01.");

   //--- live needs both switches
   g_live=(InpLive && InpAcceptRisk);
   if(InpLive && !InpAcceptRisk)
      Alert("SsalimutoProfits: InpLive is true but InpAcceptRisk is false. Running in SIGNAL-ONLY mode, no trades.");

   //--- the walk-forward pass list (tf 1d)
   //        base      on              mode          rsi  sl   mrSL  tp   bars adx  brk
   AddPair("GBPUSD", InpTradeGBPUSD, SP_MODE_MEANREV, 10, 2.5, 2.5, 3.0, 24, 25.0, 20);
   AddPair("USDCHF", InpTradeUSDCHF, SP_MODE_MEANREV,  5, 2.5, 2.5, 3.0, 12, 25.0, 20);
   AddPair("AUDUSD", InpTradeAUDUSD, SP_MODE_AUTO,    10, 2.0, 2.5, 3.0, 24, 25.0, 20);
   AddPair("EURGBP", InpTradeEURGBP, SP_MODE_MEANREV, 10, 1.5, 1.5, 3.0, 12, 25.0, 20);

   int active=0;
   for(int i=0;i<ArraySize(g_pairs);i++)
     {
      if(!g_pairs[i].enabled)
         continue;
      if(!SymbolSelect(g_pairs[i].sym,true))
        {
         Print(g_pairs[i].sym,": symbol not found at this broker. Check InpSymbolSuffix. Pair skipped.");
         g_pairs[i].enabled=false;
         continue;
        }
      string s=g_pairs[i].sym;
      g_pairs[i].hEma  =iMA(s,SP_TF,g_pairs[i].ema,0,MODE_EMA,PRICE_CLOSE);
      g_pairs[i].hSma5 =iMA(s,SP_TF,5,0,MODE_SMA,PRICE_CLOSE);
      g_pairs[i].hBands=iBands(s,SP_TF,20,0,g_pairs[i].bb_k,PRICE_CLOSE);
      g_pairs[i].hRsi  =iRSI(s,SP_TF,2,PRICE_CLOSE);
      g_pairs[i].hAdx  =iADXWilder(s,SP_TF,14);
      if(g_pairs[i].hEma==INVALID_HANDLE || g_pairs[i].hSma5==INVALID_HANDLE ||
         g_pairs[i].hBands==INVALID_HANDLE || g_pairs[i].hRsi==INVALID_HANDLE ||
         g_pairs[i].hAdx==INVALID_HANDLE)
        {
         Print(s,": could not create indicators (error ",GetLastError(),"). Pair skipped.");
         g_pairs[i].enabled=false;
         continue;
        }
      active++;
     }
   if(active==0)
     {
      Print("No pairs are active. Nothing to do.");
      return(INIT_FAILED);
     }

   g_trade.SetExpertMagicNumber((ulong)MagicNumber);
   g_trade.SetDeviationInPoints(InpSlippagePoints);
   g_trade.SetMarginMode();

   if(InpResetHalt)
     {
      GlobalVariableDel(g_gv+"halt");
      GlobalVariableSet(g_gv+"peak",AccountInfoDouble(ACCOUNT_EQUITY));
      Print("Drawdown halt cleared and equity peak reset. Set InpResetHalt back to false.");
     }

   PrintFormat("SsalimutoProfits started in %s mode. Pairs active: %d. Timeframe: D1. Lot: %.2f.",
               g_live ? "LIVE" : "SIGNAL-ONLY (no trades)",active,LotToUse());
   Print("Made by Ssali Muto. No bot can promise no losses.");

   EventSetTimer(MathMax(5,InpTimerSeconds));
   return(INIT_SUCCEEDED);
  }

//+------------------------------------------------------------------+
void OnDeinit(const int reason)
  {
   EventKillTimer();
   for(int i=0;i<ArraySize(g_pairs);i++)
     {
      if(g_pairs[i].hEma!=INVALID_HANDLE)   IndicatorRelease(g_pairs[i].hEma);
      if(g_pairs[i].hSma5!=INVALID_HANDLE)  IndicatorRelease(g_pairs[i].hSma5);
      if(g_pairs[i].hBands!=INVALID_HANDLE) IndicatorRelease(g_pairs[i].hBands);
      if(g_pairs[i].hRsi!=INVALID_HANDLE)   IndicatorRelease(g_pairs[i].hRsi);
      if(g_pairs[i].hAdx!=INVALID_HANDLE)   IndicatorRelease(g_pairs[i].hAdx);
     }
  }

//+------------------------------------------------------------------+
void OnTick()  { }   // all work is done in OnTimer, for every pair

//+------------------------------------------------------------------+
void OnTimer()
  {
   //--- account level guards
   double eq=AccountInfoDouble(ACCOUNT_EQUITY);
   UpdateDayAndPeak(eq);

   if(GlobalVariableCheck(g_gv+"halt"))
     {
      static datetime lastHaltMsg=0;
      if(TimeCurrent()-lastHaltMsg>3600)
        {
         Print("HALTED by the drawdown kill switch. No new trades. Set InpResetHalt=true once to restart.");
         lastHaltMsg=TimeCurrent();
        }
      return;
     }

   double peak=GlobalVariableGet(g_gv+"peak");
   double dd=(peak>0.0) ? (peak-eq)/peak*100.0 : 0.0;
   if(dd>=InpMaxDrawdownPct)
     {
      PrintFormat("KILL SWITCH: drawdown %.1f%% from peak %.2f (limit %.1f%%). Closing this EA's positions and halting.",
                  dd,peak,InpMaxDrawdownPct);
      CloseAllMine("drawdown kill switch");
      GlobalVariableSet(g_gv+"halt",1.0);
      return;
     }

   for(int i=0;i<ArraySize(g_pairs);i++)
      if(g_pairs[i].enabled)
         ProcessPair(i);
  }

//+------------------------------------------------------------------+
//| One pair, once per new closed D1 bar                              |
//+------------------------------------------------------------------+
void ProcessPair(const int k)
  {
   string s=g_pairs[k].sym;

   //--- enough history and indicators calculated?
   if(Bars(s,SP_TF)<WARMUP_BARS+2)
      return;
   if(BarsCalculated(g_pairs[k].hEma)<WARMUP_BARS || BarsCalculated(g_pairs[k].hAdx)<WARMUP_BARS ||
      BarsCalculated(g_pairs[k].hBands)<WARMUP_BARS || BarsCalculated(g_pairs[k].hRsi)<WARMUP_BARS ||
      BarsCalculated(g_pairs[k].hSma5)<WARMUP_BARS)
      return;

   datetime closedBar=iTime(s,SP_TF,1);
   datetime curBar=iTime(s,SP_TF,0);
   if(closedBar==0 || curBar==0)
      return;
   if(closedBar==g_pairs[k].lastDone)
      return;

   //--- read indicator values on closed bars (index 0 = shift 1)
   double ema[],sma5[],bbU[],bbL[],rsi[],adx[];
   ArraySetAsSeries(ema,true);
   ArraySetAsSeries(sma5,true);
   ArraySetAsSeries(bbU,true);
   ArraySetAsSeries(bbL,true);
   ArraySetAsSeries(rsi,true);
   ArraySetAsSeries(adx,true);
   if(CopyBuffer(g_pairs[k].hEma,0,1,5,ema)!=5)       return;   // ema[0]=bar i, ema[4]=bar i-4
   if(CopyBuffer(g_pairs[k].hSma5,0,1,1,sma5)!=1)     return;
   if(CopyBuffer(g_pairs[k].hBands,1,1,1,bbU)!=1)     return;   // 1 = UPPER_BAND
   if(CopyBuffer(g_pairs[k].hBands,2,1,1,bbL)!=1)     return;   // 2 = LOWER_BAND
   if(CopyBuffer(g_pairs[k].hRsi,0,1,1,rsi)!=1)       return;
   if(CopyBuffer(g_pairs[k].hAdx,0,1,1,adx)!=1)       return;   // 0 = MAIN_LINE
   double atr=WilderATR(s,g_pairs[k].atr);
   if(atr<=0.0)
      return;
   double c=iClose(s,SP_TF,1);
   if(c<=0.0)
      return;

   //--- 1) manage our open position on this symbol (meanrev exits)
   ulong ticket=0;
   if(FindMyPosition(s,ticket))
     {
      ManagePosition(k,ticket,c,sma5[0]);
      g_pairs[k].lastDone=closedBar;
      return;
     }

   //--- one position per symbol: also respect any other position on it
   if(AnyPositionOn(s))
     {
      g_pairs[k].lastDone=closedBar;
      return;
     }

   //--- 2) look for a new entry
   int kind=0;
   int side=0;            // +1 buy, -1 sell
   double sl_d=0.0,tp_d=0.0;
   if(!EntrySignal(k,c,ema,bbU[0],bbL[0],rsi[0],adx[0],atr,side,kind,sl_d,tp_d))
     {
      g_pairs[k].lastDone=closedBar;
      return;
     }
   string sideTxt=(side>0) ? "BUY" : "SELL";
   string kindTxt=(kind==KIND_MR) ? "mr" : "trend";

   //--- too late in the day bar? (EA started late or was offline)
   if(TimeCurrent()-curBar>InpMaxEntryDelayHours*3600)
     {
      PrintFormat("%s %s %s signal SKIPPED: the day bar opened more than %d hours ago.",s,sideTxt,kindTxt,InpMaxEntryDelayHours);
      g_pairs[k].lastDone=closedBar;
      return;
     }

   //--- guards
   string why="";
   if(!GuardsAllow(why))
     {
      PrintFormat("%s %s %s signal SKIPPED: %s",s,sideTxt,kindTxt,why);
      g_pairs[k].lastDone=closedBar;
      return;
     }

   //--- spread (just after the day opens spreads are often wide; wait, do not mark done)
   double pip=PipSize(s);
   double ask=SymbolInfoDouble(s,SYMBOL_ASK);
   double bid=SymbolInfoDouble(s,SYMBOL_BID);
   if(ask<=0.0 || bid<=0.0)
      return;
   double spreadPips=(ask-bid)/pip;
   if(spreadPips>InpMaxSpreadPips)
     {
      static datetime lastSpreadMsg=0;
      if(TimeCurrent()-lastSpreadMsg>900)
        {
         PrintFormat("%s %s signal waiting: spread %.1f pips > %.1f.",s,sideTxt,spreadPips,InpMaxSpreadPips);
         lastSpreadMsg=TimeCurrent();
        }
      return;
     }

   //--- prices, stops, lot and risk check
   int digits=(int)SymbolInfoInteger(s,SYMBOL_DIGITS);
   double entry=(side>0) ? ask : bid;
   double sl=NormalizeDouble(entry-side*sl_d,digits);
   double tp=NormalizeDouble(entry+side*tp_d,digits);

   double point=SymbolInfoDouble(s,SYMBOL_POINT);
   double minDist=(double)SymbolInfoInteger(s,SYMBOL_TRADE_STOPS_LEVEL)*point;
   if(MathAbs(entry-sl)<=minDist || MathAbs(tp-entry)<=minDist)
     {
      PrintFormat("%s signal SKIPPED: stop or target is closer than the broker minimum.",s);
      g_pairs[k].lastDone=closedBar;
      return;
     }

   double lots=0.0;
   string lotWhy="";
   if(!CheckLot(s,lots,lotWhy))
     {
      PrintFormat("%s %s signal SKIPPED: %s",s,sideTxt,lotWhy);
      g_pairs[k].lastDone=closedBar;
      return;
     }

   double risk=StopRiskMoney(s,side,lots,entry,sl);
   double bal=AccountInfoDouble(ACCOUNT_BALANCE);
   if(risk<0.0 || bal<=0.0)
     {
      PrintFormat("%s signal SKIPPED: could not work out the stop risk.",s);
      g_pairs[k].lastDone=closedBar;
      return;
     }
   double riskPct=risk/bal*100.0;
   if(riskPct>InpMaxRiskPct)
     {
      PrintFormat("%s %s signal SKIPPED: %.2f lot risks %.2f %s = %.1f%% of balance (limit %.1f%%).",
                  s,sideTxt,lots,risk,AccountInfoString(ACCOUNT_CURRENCY),riskPct,InpMaxRiskPct);
      g_pairs[k].lastDone=closedBar;
      return;
     }

   string comment="SP:"+kindTxt;
   if(!g_live)
     {
      PrintFormat("[signal only] would %s %s (%s) %.2f lot at %s  SL %s  TP %s  risk %.2f %s (%.1f%%)",
                  sideTxt,s,kindTxt,lots,DoubleToString(entry,digits),DoubleToString(sl,digits),
                  DoubleToString(tp,digits),risk,AccountInfoString(ACCOUNT_CURRENCY),riskPct);
      g_dryTradesDay++;
      g_pairs[k].lastDone=closedBar;
      return;
     }

   //--- live: last checks
   if(!TerminalInfoInteger(TERMINAL_TRADE_ALLOWED) || !MQLInfoInteger(MQL_TRADE_ALLOWED))
     {
      static datetime lastAlgoMsg=0;
      if(TimeCurrent()-lastAlgoMsg>3600)
        {
         Print("Algo Trading is OFF in the terminal or for this EA. Turn it on to trade.");
         lastAlgoMsg=TimeCurrent();
        }
      return;   // not marked done: will try again once Algo Trading is on (within the delay limit)
     }

   g_trade.SetTypeFillingBySymbol(s);
   bool ok=(side>0) ? g_trade.Buy(lots,s,0.0,sl,tp,comment)
                    : g_trade.Sell(lots,s,0.0,sl,tp,comment);
   uint rc=g_trade.ResultRetcode();
   if(ok && (rc==TRADE_RETCODE_DONE || rc==TRADE_RETCODE_PLACED || rc==TRADE_RETCODE_DONE_PARTIAL))
     {
      PrintFormat("OPENED %s %s (%s) %.2f lot  SL %s  TP %s  risk %.2f %s (%.1f%%)",
                  sideTxt,s,kindTxt,lots,DoubleToString(sl,digits),DoubleToString(tp,digits),
                  risk,AccountInfoString(ACCOUNT_CURRENCY),riskPct);
      //--- remember the kind of this position (comments can be changed by brokers)
      ulong t=0;
      if(FindMyPosition(s,t))
         GlobalVariableSet(g_gv+"k_"+IntegerToString((long)t),(double)kind);
     }
   else
     {
      PrintFormat("Order FAILED %s %s: %u %s",sideTxt,s,rc,g_trade.ResultRetcodeDescription());
     }
   g_pairs[k].lastDone=closedBar;   // never retry a failed order on the same bar
  }

//+------------------------------------------------------------------+
//| Entry rules, on the last CLOSED bar (python: entry_signal)        |
//+------------------------------------------------------------------+
bool EntrySignal(const int k,const double c,const double &ema[],const double bbU,const double bbL,
                 const double rsi,const double adx,const double atr,
                 int &side,int &kind,double &sl_d,double &tp_d)
  {
   if(g_pairs[k].mode==SP_MODE_AUTO && adx>=g_pairs[k].adx_th)
      return(TrendSignal(k,c,ema,atr,side,kind,sl_d,tp_d));

   double slMult=(g_pairs[k].mode==SP_MODE_AUTO) ? g_pairs[k].mr_sl_atr : g_pairs[k].sl_atr;
   return(MeanRevSignal(k,c,ema,bbU,bbL,rsi,atr,slMult,side,kind,sl_d,tp_d));
  }

//--- python: _mr_sig
bool MeanRevSignal(const int k,const double c,const double &ema[],const double bbU,const double bbL,
                   const double rsi,const double atr,const double slMult,
                   int &side,int &kind,double &sl_d,double &tp_d)
  {
   double lo=(double)g_pairs[k].rsi_lo;
   bool up  =(c>ema[0] && ema[0]>ema[4]);
   bool down=(c<ema[0] && ema[0]<ema[4]);
   if(up && (rsi<lo || c<bbL))
      side=1;
   else
      if(down && (rsi>100.0-lo || c>bbU))
         side=-1;
      else
         return(false);
   kind=KIND_MR;
   sl_d=slMult*atr;
   tp_d=g_pairs[k].tp_atr*atr;
   return(true);
  }

//--- python: _trend_sig (used by AUDUSD auto when ADX >= threshold)
bool TrendSignal(const int k,const double c,const double &ema[],const double atr,
                 int &side,int &kind,double &sl_d,double &tp_d)
  {
   string s=g_pairs[k].sym;
   int n=g_pairs[k].breakout;
   //--- highest high / lowest low of the n bars BEFORE the signal bar (shifts 2..n+1)
   int iHi=iHighest(s,SP_TF,MODE_HIGH,n,2);
   int iLo=iLowest(s,SP_TF,MODE_LOW,n,2);
   if(iHi<0 || iLo<0)
      return(false);
   double hi=iHigh(s,SP_TF,iHi);
   double lo=iLow(s,SP_TF,iLo);
   if(c>ema[0] && ema[0]>ema[4] && c>hi)
      side=1;
   else
      if(c<ema[0] && ema[0]<ema[4] && c<lo)
         side=-1;
      else
         return(false);
   kind=KIND_TREND;
   sl_d=g_pairs[k].sl_atr*atr;
   tp_d=g_pairs[k].tp_atr*atr;
   return(true);
  }

//+------------------------------------------------------------------+
//| Exits for mean reversion positions (python: mr_exit_now)          |
//| Trend positions use only the broker stop loss / take profit.      |
//+------------------------------------------------------------------+
void ManagePosition(const int k,const ulong ticket,const double c,const double sma5)
  {
   if(!PositionSelectByTicket(ticket))
      return;
   string s=g_pairs[k].sym;
   long type=PositionGetInteger(POSITION_TYPE);
   datetime opened=(datetime)PositionGetInteger(POSITION_TIME);

   int kind=KIND_MR;
   string key=g_gv+"k_"+IntegerToString((long)ticket);
   if(GlobalVariableCheck(key))
      kind=(int)GlobalVariableGet(key);
   else
      if(StringFind(PositionGetString(POSITION_COMMENT),"trend")>=0)
         kind=KIND_TREND;
   if(kind!=KIND_MR)
      return;

   int held=iBarShift(s,SP_TF,opened,false);   // closed bars since the entry bar
   if(held<1)
      return;
   bool buy=(type==POSITION_TYPE_BUY);
   bool exitNow=(held>=g_pairs[k].max_bars) || (buy ? (c>sma5) : (c<sma5));
   if(!exitNow)
      return;

   string why=(held>=g_pairs[k].max_bars) ? "time limit" : "close crossed back over the 5-bar average";
   if(!g_live)
     {
      PrintFormat("[signal only] would close %s position %I64u (%s).",s,ticket,why);
      return;
     }
   if(g_trade.PositionClose(ticket,(ulong)InpSlippagePoints))
     {
      PrintFormat("CLOSED %s position %I64u (%s).",s,ticket,why);
      GlobalVariableDel(key);
     }
   else
      PrintFormat("Close FAILED %s %I64u: %u %s",s,ticket,g_trade.ResultRetcode(),g_trade.ResultRetcodeDescription());
  }

//+------------------------------------------------------------------+
//| Guards (python: guard_reasons)                                    |
//+------------------------------------------------------------------+
bool GuardsAllow(string &why)
  {
   if(FileIsExist(STOP_FILE))
     {
      why="STOP file present (MQL5\\Files\\"+STOP_FILE+")";
      return(false);
     }
   double eq=AccountInfoDouble(ACCOUNT_EQUITY);
   double dayStart=GlobalVariableGet(g_gv+"daystart");
   double dl=(dayStart>0.0) ? (dayStart-eq)/dayStart*100.0 : 0.0;
   if(dl>=InpDailyLossPct)
     {
      why=StringFormat("daily loss %.1f%% >= %.1f%%",dl,InpDailyLossPct);
      return(false);
     }
   int today=TradesToday();
   if(today>=InpMaxTradesPerDay)
     {
      why=StringFormat("max trades for today reached (%d/%d)",today,InpMaxTradesPerDay);
      return(false);
     }
   return(true);
  }

//--- start of the broker's day
datetime DayStart()
  {
   MqlDateTime t;
   TimeToStruct(TimeCurrent(),t);
   t.hour=0;
   t.min=0;
   t.sec=0;
   return(StructToTime(t));
  }

//--- day start equity and equity peak, kept in terminal global variables
void UpdateDayAndPeak(const double eq)
  {
   double dayKey=(double)DayStart();
   if(!GlobalVariableCheck(g_gv+"day") || GlobalVariableGet(g_gv+"day")!=dayKey)
     {
      GlobalVariableSet(g_gv+"day",dayKey);
      GlobalVariableSet(g_gv+"daystart",eq);
     }
   if(!GlobalVariableCheck(g_gv+"peak") || eq>GlobalVariableGet(g_gv+"peak"))
      GlobalVariableSet(g_gv+"peak",eq);

   string d=TimeToString(DayStart(),TIME_DATE);
   if(d!=g_dryDay)
     {
      g_dryDay=d;
      g_dryTradesDay=0;
     }
  }

//--- new trades opened today by this EA (live), or signals taken today (signal-only)
int TradesToday()
  {
   if(!g_live)
      return(g_dryTradesDay);
   int n=0;
   if(!HistorySelect(DayStart(),TimeCurrent()+60))
      return(n);
   int total=HistoryDealsTotal();
   for(int i=0;i<total;i++)
     {
      ulong d=HistoryDealGetTicket(i);
      if(d==0)
         continue;
      if(HistoryDealGetInteger(d,DEAL_MAGIC)!=MagicNumber)
         continue;
      if(HistoryDealGetInteger(d,DEAL_ENTRY)==DEAL_ENTRY_IN)
         n++;
     }
   return(n);
  }

//+------------------------------------------------------------------+
//| Positions                                                         |
//+------------------------------------------------------------------+
bool FindMyPosition(const string s,ulong &ticket)
  {
   for(int i=PositionsTotal()-1;i>=0;i--)
     {
      ulong t=PositionGetTicket(i);
      if(t==0)
         continue;
      if(PositionGetString(POSITION_SYMBOL)==s && PositionGetInteger(POSITION_MAGIC)==MagicNumber)
        {
         ticket=t;
         return(true);
        }
     }
   return(false);
  }

bool AnyPositionOn(const string s)
  {
   for(int i=PositionsTotal()-1;i>=0;i--)
     {
      ulong t=PositionGetTicket(i);
      if(t!=0 && PositionGetString(POSITION_SYMBOL)==s)
         return(true);
     }
   return(false);
  }

void CloseAllMine(const string why)
  {
   for(int i=PositionsTotal()-1;i>=0;i--)
     {
      ulong t=PositionGetTicket(i);
      if(t==0 || PositionGetInteger(POSITION_MAGIC)!=MagicNumber)
         continue;
      string s=PositionGetString(POSITION_SYMBOL);
      if(!g_live)
        {
         PrintFormat("[signal only] would close %s position %I64u (%s).",s,t,why);
         continue;
        }
      if(g_trade.PositionClose(t,(ulong)InpSlippagePoints))
         PrintFormat("CLOSED %s position %I64u (%s).",s,t,why);
      else
         PrintFormat("Close FAILED %s %I64u: %u %s",s,t,g_trade.ResultRetcode(),g_trade.ResultRetcodeDescription());
     }
  }

//+------------------------------------------------------------------+
//| Lot size: fixed, never above 0.01, never increased after a loss   |
//+------------------------------------------------------------------+
double LotToUse()
  {
   return(MathMin(InpLots,MAX_LOT));
  }

bool CheckLot(const string s,double &lots,string &why)
  {
   double vmin =SymbolInfoDouble(s,SYMBOL_VOLUME_MIN);
   double vstep=SymbolInfoDouble(s,SYMBOL_VOLUME_STEP);
   lots=LotToUse();
   if(vstep>0.0)
      lots=MathFloor(lots/vstep+1e-9)*vstep;
   lots=NormalizeDouble(lots,2);
   if(lots>MAX_LOT)
      lots=MAX_LOT;
   if(vmin>MAX_LOT+1e-9)
     {
      why=StringFormat("broker minimum lot is %.2f, above the 0.01 cap",vmin);
      return(false);
     }
   if(lots<vmin-1e-9)
     {
      why=StringFormat("lot %.2f is below the broker minimum %.2f",lots,vmin);
      return(false);
     }
   return(true);
  }

//--- money lost (account currency) if the stop is hit
double StopRiskMoney(const string s,const int side,const double lots,const double entry,const double sl)
  {
   double profit=0.0;
   ENUM_ORDER_TYPE t=(side>0) ? ORDER_TYPE_BUY : ORDER_TYPE_SELL;
   if(!OrderCalcProfit(t,s,lots,entry,sl,profit))
      return(-1.0);
   return(MathAbs(profit));
  }

//+------------------------------------------------------------------+
//| Helpers                                                           |
//+------------------------------------------------------------------+
double PipSize(const string s)
  {
   int digits=(int)SymbolInfoInteger(s,SYMBOL_DIGITS);
   double point=SymbolInfoDouble(s,SYMBOL_POINT);
   return((digits==3 || digits==5) ? point*10.0 : point);
  }

//--- Wilder ATR on closed bars, same as the python bot (MT5 iATR uses a simple average)
double WilderATR(const string s,const int n)
  {
   MqlRates r[];
   ArraySetAsSeries(r,false);                   // oldest first
   int got=CopyRates(s,SP_TF,1,ATR_BARS,r);        // last element = last closed bar
   if(got<n+2)
      return(0.0);
   double a=0.0;
   for(int i=0;i<got;i++)
     {
      double pc=(i>0) ? r[i-1].close : r[i].close;
      double tr=MathMax(r[i].high-r[i].low,MathMax(MathAbs(r[i].high-pc),MathAbs(r[i].low-pc)));
      a=(i==0) ? tr : (a*(n-1)+tr)/n;
     }
   return(a);
  }
//+------------------------------------------------------------------+
