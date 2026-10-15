# Hissab — V1 SaaS

Gestion simple pour commerces et PME d'Afrique francophone : **stock, facturation, caisse**, multi-entreprises.
« Vos chiffres, clairs chaque soir. »

## Démarrage rapide (Docker)

Prérequis : Docker Desktop (ou Docker Engine + Compose v2).

```bash
cp .env.example .env
# Éditez .env : DJANGO_SECRET_KEY et POSTGRES_PASSWORD (valeurs longues et aléatoires)
docker compose up -d --build
```

Ouvrez http://localhost:8000/inscription/ et créez votre entreprise.
Les migrations s'appliquent automatiquement au démarrage.

Commandes utiles :

| Action | Commande |
|---|---|
| Voir les logs | `docker compose logs -f web` |
| Créer un super-administrateur (accès `/admin/`) | `docker compose exec web python manage.py createsuperuser` |
| Lancer les tests | `docker compose exec web python manage.py test` |
| Sauvegarder la base | `docker compose exec db pg_dump -U hissab hissab > sauvegarde.sql` |
| Arrêter | `docker compose down` (les données restent dans le volume `pgdata`) |

## Fonctionnalités

| Module | Contenu |
|---|---|
| Comptes | Inscription = création de l'entreprise ; rôles Gérant / Employé ; paramètres (NIF, Bankily, Masrvi, TVA, fond de caisse) |
| Stock | Produits, stock de départ, entrées/sorties, statut OK / À commander / Rupture, valeur du stock |
| Facturation | Clients, factures numérotées sans doublon (`FAC-2026-0001`), remises, TVA, impression/PDF, paiements partiels, statuts (À encaisser, Partielle, En retard, Payée) |
| Caisse | Ventes (retirent le stock automatiquement), dépenses, apports/retraits, clôture journalière avec écart |
| Tableau de bord | Ventes, encaissements, dépenses, résultat de trésorerie, créances, retards, alertes stock, encaissements par mode |

Règles métier importantes :
- Seules les opérations **en espèces** (ventes, paiements de factures, dépenses, apports/retraits) entrent dans la clôture de caisse.
- L'ouverture d'une journée = espèces comptées à la clôture précédente, sinon le fond de caisse de départ.
- Une **facture ne retire pas le stock** (évite le double comptage avec la caisse) : enregistrez une sortie de stock si la marchandise facturée est livrée.
- Suppressions réservées au gérant ; un produit, client ou facture déjà utilisé ne peut pas être supprimé.

## Architecture

```
config/      réglages (tout vient des variables d'environnement), URLs, WSGI
accounts/    Organization, Membership, isolation multi-entreprises (middleware + mixins), tableau de bord
inventory/   Product, StockMovement
billing/     Customer, Invoice, InvoiceLine, Payment
cash/        Sale, Expense, CashMovement, CashClosing
templates/   interface (rendu serveur, sans build JavaScript)
```

Isolation des données : chaque enregistrement porte `organization` ; toutes les vues passent par
`OrgScopedMixin` (filtrage du queryset → 404 pour les données d'une autre entreprise) et les formulaires
ne proposent que les produits, clients et factures de l'entreprise courante. Couvert par les tests `TenantIsolationTests`.

Stack : Django 5.2 LTS · PostgreSQL 16 · Gunicorn · WhiteNoise · Docker Compose.

## Développement sans Docker

```bash
python -m venv .venv && . .venv/bin/activate
pip install -r requirements.txt
DJANGO_DEBUG=1 python manage.py migrate
DJANGO_DEBUG=1 python manage.py runserver
DJANGO_DEBUG=1 python manage.py test
```
(SQLite est utilisé si `DATABASE_URL` n'est pas défini.)

## Mise en production — checklist

- [ ] `.env` : `DJANGO_DEBUG=0`, clé secrète unique, mot de passe Postgres fort, `DJANGO_ALLOWED_HOSTS` et `DJANGO_CSRF_TRUSTED_ORIGINS` = votre domaine
- [ ] Reverse proxy HTTPS devant le port 8000 (Caddy ou Nginx + Let's Encrypt), puis `DJANGO_BEHIND_PROXY=1`, `DJANGO_SECURE_SSL_REDIRECT=1`, `DJANGO_SECURE_COOKIES=1`, `DJANGO_HSTS_SECONDS=31536000`
- [ ] Sauvegarde quotidienne de la base (`pg_dump`) copiée hors du serveur, et test de restauration
- [ ] Ne pas exposer le port 5432
- [ ] Limiter les tentatives de connexion (ex. `django-axes` ou règle du reverse proxy) — non inclus en V1

## Limites connues de la V1

- Pas de paiement mobile money automatique (les paiements sont saisis à la main avec leur référence).
- Pas de montant en lettres sur la facture, ni d'avoir (les quantités doivent être positives) : corrigez une facture en la modifiant tant qu'elle n'est pas payée.
- Pas de limitation des tentatives de connexion ni de réinitialisation de mot de passe par e-mail.
- Une facture ne mouvemente pas le stock.
- Un utilisateur appartient à une seule entreprise.
