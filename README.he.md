<div dir="rtl">

<p align="center"><img src="docs/banner.svg" alt="il-basket-compare" width="100%"></p>

<p align="center">
  <a href="https://github.com/Shtibel1/il-basket-compare/actions/workflows/ci.yml"><img src="https://github.com/Shtibel1/il-basket-compare/actions/workflows/ci.yml/badge.svg" alt="CI"></a>
  <a href="LICENSE"><img src="https://img.shields.io/badge/license-MIT-blue.svg" alt="MIT"></a>
  <a href="README.md"><img src="https://img.shields.io/badge/README-English-0f5b45" alt="English"></a>
</p>

# il-basket-compare

תבנית לאתר השוואת מחירי סל קניות לכל עיר בישראל. בונים סל ורואים באיזה סופר בעיר הוא יוצא הכי זול. המחירים מגיעים מקובצי המחירים שהרשתות הגדולות חייבות לפרסם לפי חוק שקיפות המחירים. ריצה יומית של GitHub Actions מורידה אותם, והאתר מתארח ב-GitHub Pages, בלי שרתים, בלי מסד נתונים ובלי מפתחות.

<p align="center">
  <img src="docs/screenshot-desktop.png" alt="תצוגת מחשב" width="72%">
  <img src="docs/screenshot-mobile.png" alt="תצוגת נייד" width="22%">
</p>

## מה יש

- 18 רשתות דרך 4 פורטלים: שופרסל, קרפור, רמי לוי, יוחננוף, אושר עד, טיב טעם ועוד.
- השוואה לפי ברקוד למוצרים ארוזים, והשוואה לפי שם לעוף, בשר, פירות וירקות (בכל סופר נלקח הפריט המתאים הזול ביותר).
- מבצעים שפתוחים לכל הלקוחות, בלי מבצעי מועדון, אשראי וקופונים.
- דירוג לפי רשת או לפי סניף, פירוט סל, מצב כהה ותמיכה מלאה בנייד.
- הכול מוגדר בקובץ אחד, `site.config.json`: עיר, רשתות ומיתוג.
- אשף התקנה, `python -m pricecompare init`, שמוצא את סמל היישוב של הלמ״ס ואת הסניפים של כל רשת.

## התחלה מהירה

**בלי להתקין כלום**

1. לוחצים **Use this template** (או Fork).
2. מעדכנים את `site.config.json` לעיר שלכם, או מריצים את האשף מקומית ומעלים את הקובץ שנוצר.
3. ב-**Settings → Pages** בוחרים **Source: GitHub Actions**.
4. ב-**Actions → Update prices and deploy** לוחצים **Run workflow**. האתר עולה בכתובת `https://<you>.github.io/<repo>/` ומתעדכן כל יום.

**מקומית**

```bash
pip install -r requirements.txt
python -m pricecompare init      # למשל: נתניה
python -m pricecompare update    # הורדת המחירים של היום
python -m pricecompare serve     # http://localhost:8000
```

לפני `update`, האתר מציג את נתוני הדוגמה שבריפו (`web/sample-data.json`), כך שאפשר לראות את הממשק גם בלי אינטרנט.

## הוספת רשת או פורטל

- **רשת בפורטל שכבר נתמך**: מוסיפים שורה ל-`CHAINS` בקובץ `pricecompare/chains.py`.
- **פורטל חדש**: מוסיפים מחלקה ב-`pricecompare/sources.py` עם `stores()`, `latest_price_files()` ו-`latest_promo_files()`, רושמים אותה ב-`source_for()` ומוסיפים בדיקה.

## הערה משפטית

המחירים ציבוריים ומתפרסמים לפי חוק לקידום התחרות בענף המזון (שקיפות מחירים), התשע״ד-2014. הפרויקט רק מוריד את הקבצים מהפורטלים הציבוריים של הרשתות, ואינו קשור לאף רשת. המחירים עלולים להתעדכן באיחור או להכיל טעויות, אז כדאי לבדוק בחנות. תמונות מוצרים **כבויות כברירת מחדל**, כי הן מוגנות בזכויות יוצרים ואינן חלק מהמידע שמתפרסם לפי החוק. אם מפעילים `"images": true`, האחריות לוודא שמותר להשתמש במקור התמונות היא עליכם.

## תוכנית המשך

- פורטלים נוספים (ויקטורי, מחסני השוק, חצי חינם)
- כמה ערים באתר אחד, עם בחירת עיר
- היסטוריית מחירים
- קישור לשיתוף סל
- ממשק באנגלית

## רישיון

[MIT](LICENSE) © Nadav Shtibel

</div>
