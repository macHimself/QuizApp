# 🧠 Quiz App

Tato aplikace je jednoduchý systém pro správu a testování otázek v tematických okruzích. Umožňuje:

- Vytvářet tematické okruhy
- Přidávat otázky (jednotlivě i hromadně)
- Odpovídat na otázky a hodnotit si je
- Zobrazovat statistiky včetně pokroku a průměrného hodnocení
- Spravovat historii a resetovat data

## 🚀 Spuštění

```bash
python app.py
```

Aplikace poběží na `http://127.0.0.1:5000`.

## 🛠️ Požadavky

- Python 3.10+
- Flask

```bash
pip install flask
```

## 📁 Struktura

- `app.py` – hlavní Flask aplikace
- `data/` – JSON soubory s otázkami, statistikami a historií
- `templates/` – HTML šablony
- `static/` – volitelně pro styl nebo JavaScript

## 📄 Licence

Tento projekt je pod licencí [MIT](LICENSE).  
Můžeš ho volně používat, upravovat i distribuovat. Nenesu však žádnou zodpovědnost za použití tohoto softwaru.

---

Pokud chceš přispět nebo hlásit chybu, klidně vytvoř [issue](https://github.com/macHimself/QuizApp/issues) nebo forkni repozitář.
