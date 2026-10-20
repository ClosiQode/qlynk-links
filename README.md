# Qlynk Links, skill Claude

Français | [English](#english)

Un skill pour Claude.ai et Claude Code qui pilote votre compte [Qlynk](https://qlynk.eu), le raccourcisseur de liens français, en langage courant : « raccourcis ce lien », « crée le QR code », « combien de clics cette semaine ? ».

## Ce que fait le skill

- Créer des liens courts, avec une fin personnalisée (`qlynk.eu/soldes-ete`).
- Créer le QR code d'un lien, en PNG ou en SVG. Il est calculé sur place par le script, sans service extérieur.
- Lire les clics d'un lien ou de tous vos liens, par jour, semaine, mois ou année.
- Ranger les liens dans des catégories et des sous-catégories.
- Modifier, renommer et supprimer des liens (Claude demande confirmation avant de supprimer).

Le skill appelle l'API REST de Qlynk avec votre clé. Les erreurs 401 (clé refusée), 429 (limite atteinte) et les limites d'offre sont expliquées clairement. Python 3 suffit, sans dépendance.

## Contenu

```
qlynk-links/
  SKILL.md             instructions lues par Claude
  scripts/qlynk.py     client de l'API
  scripts/qr.py        génération du QR code
  references/api.md    référence de l'API
```

Tout est lisible : vous pouvez vérifier ce que fait le skill avant de l'installer.

## Clé API

1. Connectez-vous à Qlynk (un compte gratuit suffit).
2. Créez une clé sur [https://qlynk.eu/api-keys.php](https://qlynk.eu/api-keys.php). Elle n'est affichée qu'une fois : copiez-la tout de suite.
3. Le script la lit dans la variable d'environnement `QLYNK_API_KEY` et ne l'affiche jamais. Vous pouvez la révoquer à tout moment.

## Installation

### Dans Claude.ai ou l'application Claude

1. Créez votre clé API (voir ci-dessus).
2. Téléchargez le skill en `.zip` sur [https://qlynk.eu/outils/skill-claude/](https://qlynk.eu/outils/skill-claude/), sans le décompresser. Vous pouvez aussi zipper le dossier `qlynk-links/` de ce dépôt.
3. Dans Claude, ouvrez Réglages, puis Capacités. Activez l'exécution de code avec l'accès au réseau, et ajoutez `qlynk.eu` aux domaines autorisés.
4. Dans la partie Skills, choisissez « Importer un skill » et sélectionnez le fichier `.zip`.
5. Dans une conversation, collez votre clé quand Claude la demande, puis écrivez votre demande.

### Dans Claude Code (skills personnels)

1. Créez votre clé API.
2. Copiez le dossier `qlynk-links/` dans vos skills personnels :

   ```bash
   git clone https://github.com/ClosiQode/qlynk-links.git
   mkdir -p ~/.claude/skills && cp -R qlynk-links/qlynk-links ~/.claude/skills/
   ```

3. Donnez la clé à Claude Code, une fois pour toutes, dans `~/.claude/settings.json` :

   ```json
   {
     "env": { "QLYNK_API_KEY": "votre-clé-api" }
   }
   ```

4. Relancez Claude Code et demandez : « raccourcis https://… avec Qlynk ».

## Offres et quotas

Chaque action passe par l'API de Qlynk et compte dans un quota de requêtes par jour, qui dépend de l'offre (Gratuit ou Pro). Le QR code, calculé sur place, ne compte pas. Les limites et les tarifs à jour sont sur [https://qlynk.eu/#offres](https://qlynk.eu/#offres). Quand une limite est atteinte, Claude le dit et indique quand réessayer.

## Liens

- Page du skill : [https://qlynk.eu/outils/skill-claude/](https://qlynk.eu/outils/skill-claude/)
- Documentation de l'API : [https://qlynk.eu/docs/api.php](https://qlynk.eu/docs/api.php)
- Clés API : [https://qlynk.eu/api-keys.php](https://qlynk.eu/api-keys.php)

## Licence

MIT, voir [LICENSE](LICENSE). Skill publié par ClosiQode (Fabien Kost).

---

## English

A skill for Claude.ai and Claude Code that drives your [Qlynk](https://qlynk.eu) account (a French URL shortener) in plain language: "shorten this link", "make the QR code", "how many clicks this week?".

### What it does

- Create short links, with a custom ending (`qlynk.eu/summer-sale`).
- Make the QR code of a link, as PNG or SVG. It is computed locally by the script, with no external service.
- Read clicks for one link or all your links, by day, week, month or year.
- Organise links into categories and sub-categories.
- Edit, rename and delete links (Claude asks for confirmation before deleting).

The skill calls the Qlynk REST API with your key. 401 (key rejected) and 429 (limit reached) errors and plan limits are explained clearly. Python 3 is enough, no dependencies.

### Contents

```
qlynk-links/
  SKILL.md             instructions read by Claude
  scripts/qlynk.py     API client
  scripts/qr.py        QR code generation
  references/api.md    API reference
```

Everything is readable, so you can check what the skill does before installing it.

### API key

1. Log in to Qlynk (a free account is enough).
2. Create a key at [https://qlynk.eu/api-keys.php](https://qlynk.eu/api-keys.php). It is shown only once: copy it right away.
3. The script reads it from the `QLYNK_API_KEY` environment variable and never prints it. You can revoke it at any time.

### Installation

#### In Claude.ai or the Claude app

1. Create your API key (see above).
2. Download the skill as a `.zip` from [https://qlynk.eu/outils/skill-claude/](https://qlynk.eu/outils/skill-claude/), without unzipping it. You can also zip the `qlynk-links/` folder of this repository.
3. In Claude, open Settings, then Capabilities. Enable code execution with network access, and add `qlynk.eu` to the allowed domains.
4. In the Skills section, choose "Upload skill" and select the `.zip` file.
5. In a conversation, paste your key when Claude asks for it, then write your request.

#### In Claude Code (personal skills)

1. Create your API key.
2. Copy the `qlynk-links/` folder into your personal skills:

   ```bash
   git clone https://github.com/ClosiQode/qlynk-links.git
   mkdir -p ~/.claude/skills && cp -R qlynk-links/qlynk-links ~/.claude/skills/
   ```

3. Give the key to Claude Code once and for all in `~/.claude/settings.json`:

   ```json
   {
     "env": { "QLYNK_API_KEY": "your-api-key" }
   }
   ```

4. Restart Claude Code and ask: "shorten https://… with Qlynk".

### Plans and quotas

Every action goes through the Qlynk API and counts toward a daily request quota that depends on your plan (Free or Pro). The QR code, computed locally, does not count. Current limits and pricing are at [https://qlynk.eu/#offres](https://qlynk.eu/#offres). When a limit is reached, Claude says so and tells you when to retry.

### Links

- Skill page: [https://qlynk.eu/outils/skill-claude/](https://qlynk.eu/outils/skill-claude/)
- API documentation: [https://qlynk.eu/docs/api.php](https://qlynk.eu/docs/api.php)
- API keys: [https://qlynk.eu/api-keys.php](https://qlynk.eu/api-keys.php)

### License

MIT, see [LICENSE](LICENSE). Skill published by ClosiQode (Fabien Kost).
