"""
تطبيق الإشارات (Streamlit). محتاج معاه: scanner.py و requirements.txt
تعليمي فقط، مش نصيحة مالية ومفيش ضمان ربح.
"""
from datetime import datetime, timezone
import streamlit as st
import scanner as sc

st.set_page_config(page_title="ماسح الإشارات", page_icon="📈", layout="centered")
st.markdown("""
<style>
html, body, [class*='css'] {direction: rtl; text-align: right;}
.card {border-radius: 18px; padding: 18px; margin: 14px 0; background: #111827; color: #fff;
       border: 2px solid var(--c);}
.dir {font-size: 34px; font-weight: 800; color: var(--c);}
.pair {font-size: 20px; font-weight: 700;}
.row {display: flex; justify-content: space-between; margin-top: 10px; font-size: 15px; color: #d1d5db;}
.warn {margin-top: 12px; padding: 10px; border-radius: 10px; background: #3b2a12; color: #fbbf24; font-size: 14px;}
.ok {margin-top: 12px; padding: 10px; border-radius: 10px; background: #0f2f1f; color: #86efac; font-size: 14px;}
.no {margin-top: 12px; padding: 10px; border-radius: 10px; background: #2f1515; color: #fca5a5; font-size: 14px;}
</style>
""", unsafe_allow_html=True)

st.title("📈 ماسح الإشارات")
st.caption(f"فريم {sc.INTERVAL} • استراتيجية Bollinger • مدد الصفقة "
           f"{' / '.join(map(str, sc.DURATIONS_MIN))} دقيقة")

min_rate = st.slider("الحد الأدنى لنسبة النجاح التاريخية %", 0, 90, int(sc.MIN_WINRATE))
st.caption(f"نقطة التعادل مع عائد {int(sc.PAYOUT * 100)}% هي {sc.BREAKEVEN:.1f}%. "
           "أي نسبة أقل منها معناها خسارة على المدى الطويل.")


@st.cache_data(ttl=120, show_spinner=False)
def scan():
    rows, errors = [], []
    for name, sym in sc.PAIRS.items():
        try:
            rows.append(sc.analyze(name, sym))
        except Exception as e:
            errors.append(f"{name}: {e}")
    return rows, errors


def candle_countdown():
    m = sc.MINUTES[sc.INTERVAL]
    now = datetime.now(timezone.utc)
    rem = m * 60 - ((now.minute % m) * 60 + now.second)
    return f"{rem // 60}:{rem % 60:02d}"


def card(r, status, mins):
    color = {"BUY": "#22c55e", "SELL": "#ef4444", "WAIT": "#6b7280"}[r["signal"]]
    word = {"BUY": "صعود 🟢", "SELL": "هبوط 🔴", "WAIT": "انتظار ⚪"}[r["signal"]]
    below = ('<div class="warn">⚠️ نجاحه التاريخي أقل من نقطة التعادل، يعني خاسر على المدى الطويل. '
             'استخدمه للتدريب فقط.</div>') if r["test"] < sc.BREAKEVEN else ""
    st.markdown(f"""
<div class="card" style="--c:{color}">
  <div class="pair">{r['pair']}</div>
  <div class="dir">{word}</div>
  <div class="row"><span>المدة: {r['horizon'] * mins} دقيقة</span><span>السعر: {r['price']:.5f}</span></div>
  <div class="row"><span>نجاح تاريخي: {r['test']:.1f}%</span><span>على {r['test_n']} صفقة</span></div>
  <div class="row"><span>تغير 4 ساعات: {r['chg4h']:+.3f}%</span><span>RSI {r['rsi']:.0f}</span></div>
  <div class="row"><span>{r['variant']}</span><span>الشمعة تقفل بعد {candle_countdown()}</span></div>
  {below}{status}
</div>""", unsafe_allow_html=True)


if st.button("🔍 افحص الآن", use_container_width=True, type="primary"):
    scan.clear()
    st.session_state["go"] = True

if st.session_state.get("go"):
    with st.spinner("بيفحص الأزواج..."):
        rows, errors = scan()
    rows = [r for r in rows if r["horizon"] and r["test_n"] >= sc.MIN_TEST_TRADES]
    if not rows:
        st.warning("مفيش بيانات أو إشارات كفاية دلوقتي. جرّب وقت السوق مفتوح فيه.")
    rows.sort(key=lambda x: (x["signal"] != "WAIT", x["test"]), reverse=True)
    mins = sc.MINUTES[sc.INTERVAL]
    any_ok = False

    for r in rows[:sc.TOP_N]:
        nw = sc.news_check(r["sym"])
        news_bad = bool(nw and nw["high"])
        ok = r["signal"] != "WAIT" and r["test"] >= min_rate and not news_bad
        any_ok |= ok
        if ok:
            status = '<div class="ok">✅ فيه إشارة. ادخل بعد إغلاق الشمعة وبمبلغ صغير (1% كحد أقصى).</div>'
        else:
            why = []
            if r["signal"] == "WAIT":
                why.append("مفيش إشارة دلوقتي")
            if r["test"] < min_rate:
                why.append(f"نجاحه {r['test']:.0f}% أقل من {min_rate}%")
            if news_bad:
                why.append("أخبار مؤثرة: " + nw["high"][0][:60])
            status = '<div class="no">⛔ لا تدخل: ' + " + ".join(why) + "</div>"
        card(r, status, mins)

    if rows and not any_ok:
        st.info("مفيش صفقة تستوفي الشروط دلوقتي. الانتظار قرار سليم.")
    for e in errors:
        st.caption("تعذّر " + e)

st.divider()
st.caption("⚠️ تعليمي فقط، مش نصيحة مالية ومفيش ضمان ربح. جرّب على Demo، وخاطر بـ1% أو أقل، "
           "ووقّف اليوم بعد 3 خسارات ورا بعض.")
