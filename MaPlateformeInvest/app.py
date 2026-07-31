from datetime import datetime
import os
from flask import Flask, redirect, render_template, request, session, url_for
from flask_sqlalchemy import SQLAlchemy

app = Flask(__name__)
app.secret_key = "votre_cle_secrete_ultra_securisee"

# Configuration de la base de données (PostgreSQL sur Render ou SQLite en local)
database_url = os.environ.get("DATABASE_URL")
if database_url and database_url.startswith("postgres://"):
    database_url = database_url.replace("postgres://", "postgresql://", 1)

app.config["SQLALCHEMY_DATABASE_URI"] = database_url or "sqlite:///plateforme.db"
db = SQLAlchemy(app)

# --- MODÈLES DE DONNÉES ---
class Utilisateur(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    telephone = db.Column(db.String(20), unique=True, nullable=False)
    password = db.Column(db.String(100), nullable=False)
    solde = db.Column(db.Float, default=0.0)
    niveau_actuel = db.Column(db.Integer, default=0)  # 0 = Aucun niveau
    parrain_id = db.Column(db.Integer, nullable=True)
    est_premier_depot = db.Column(db.Boolean, default=True)
    est_bloque = db.Column(db.Boolean, default=False)
    total_recharge = db.Column(db.Float, default=0.0)
    total_retrait = db.Column(db.Float, default=0.0)

class Depot(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    montant = db.Column(db.Float, nullable=False)
    user_id = db.Column(db.Integer, nullable=False)
    operateur = db.Column(db.String(50), nullable=False)
    id_transaction = db.Column(db.String(100), nullable=False)
    statut = db.Column(db.String(20), default="En attente")

class Retrait(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    montant = db.Column(db.Float, nullable=False)  # Montant net
    montant_brut = db.Column(db.Float, nullable=False)
    user_id = db.Column(db.Integer, nullable=False)
    statut = db.Column(db.String(20), default="En attente")
    date_creation = db.Column(db.DateTime, default=datetime.utcnow)

# --- ROUTES AUTHENTIFICATION ---
@app.route("/")
def index():
    return redirect(url_for("login_user"))

@app.route("/inscription", methods=["GET", "POST"])
def inscription():
    if request.method == "POST":
        tel = request.form["telephone"]
        pwd = request.form["password"]
        parrain_code = request.form.get("parrain_id")

        parrain = None
        if parrain_code:
            parrain = Utilisateur.query.filter_by(id=parrain_code).first()

        new_user = Utilisateur(
            telephone=tel, password=pwd, parrain_id=parrain.id if parrain else None
        )
        db.session.add(new_user)
        db.session.commit()
        return redirect(url_for("login_user"))
    return render_template("inscription.html")

@app.route("/login_user", methods=["GET", "POST"])
def login_user():
    if request.method == "POST":
        tel = request.form["telephone"]
        pwd = request.form["password"]

        # Connexion Admin mise à jour
        if tel == "kosmaRoukaya" and pwd == "15062003admiN2001":
            session["telephone"] = "kosmaRoukaya"
            return redirect(url_for("admin_panel"))

        user = Utilisateur.query.filter_by(telephone=tel, password=pwd).first()
        if user:
            if user.est_bloque:
                return "Votre compte a été bloqué suite à une infraction. Contactez l'administrateur."
            session["user_id"] = user.id
            session["telephone"] = user.telephone
            return redirect(url_for("tableau_bord"))
    return render_template("login_user.html")

@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("login_user"))

# --- ROUTES UTILISATEUR (5 MENUS) ---
@app.route("/tableau_bord")
def tableau_bord():
    if "user_id" not in session:
        return redirect(url_for("login_user"))
    user = db.session.get(Utilisateur, session["user_id"])
    return render_template("tableau_bord.html", user=user)

@app.route("/depot", methods=["GET", "POST"])
def depot():
    if "user_id" not in session:
        return redirect(url_for("login_user"))
    user = db.session.get(Utilisateur, session["user_id"])

    message = None
    if request.method == "POST":
        operateur = request.form["operateur"]
        montant = float(request.form["montant"])
        id_trans = request.form["id_transaction"]

        nouveau_depot = Depot(
            montant=montant,
            user_id=user.id,
            operateur=operateur,
            id_transaction=id_trans,
        )
        db.session.add(nouveau_depot)
        db.session.commit()
        message = "Demande de dépôt soumise avec succès. En attente de validation."
        return render_template("resultat.html", message=message)

    return render_template("depot.html", user=user)

@app.route("/investir", methods=["GET", "POST"])
def investir():
    if "user_id" not in session:
        return redirect(url_for("login_user"))
    user = db.session.get(Utilisateur, session["user_id"])

    niveaux = {
        1: {"cout": 5000, "gain": 200},
        2: {"cout": 10000, "gain": 400},
        3: {"cout": 15000, "gain": 700},
        4: {"cout": 20000, "gain": 1000},
        5: {"cout": 30000, "gain": 1500},
        6: {"cout": 50000, "gain": 2700},
        7: {"cout": 100000, "gain": 5500},
    }

    message = None
    if request.method == "POST":
        niveau_choisi = int(request.form["niveau"])
        cout = niveaux[niveau_choisi]["cout"]

        if user.solde >= cout:
            user.solde -= cout
            user.niveau_actuel = niveau_choisi
            db.session.commit()
            message = "Investissement validé avec succès !"
        else:
            message = "SOLDE INSUFFISANT"

    return render_template("investir.html", user=user, niveaux=niveaux, message=message)

@app.route("/retrait", methods=["GET", "POST"])
def retrait():
    if "user_id" not in session:
        return redirect(url_for("login_user"))
    user = db.session.get(Utilisateur, session["user_id"])

    message = None
    if request.method == "POST":
        montant_brut = float(request.form["montant"])

        if user.niveau_actuel == 0:
            message = "Erreur : Vous devez investir avant de pouvoir effectuer un retrait."
        elif not (2500 <= montant_brut <= 50000):
            message = "Erreur : Le montant de retrait doit être compris entre 2500F et 50000F."
        else:
            debut_mois = datetime.utcnow().replace(day=1, hour=0, minute=0, second=0, microsecond=0)
            retraits_ce_mois = Retrait.query.filter(
                Retrait.user_id == user.id, Retrait.date_creation >= debut_mois
            ).count()

            if retraits_ce_mois >= 3:
                message = "Erreur : Vous avez atteint la limite de 3 retraits par mois."
            else:
                montant_net = montant_brut * 0.8
                nouveau_retrait = Retrait(
                    montant=montant_net, montant_brut=montant_brut, user_id=user.id
                )
                db.session.add(nouveau_retrait)
                db.session.commit()
                message = "Demande de retrait soumise avec succès."

    return render_template("retrait.html", user=user, message=message)

@app.route("/contact")
def contact():
    if "user_id" not in session:
        return redirect(url_for("login_user"))
    user = db.session.get(Utilisateur, session["user_id"])
    return render_template("contact.html", user=user)

@app.route("/historique_depots")
def historique_depots():
    if "user_id" not in session:
        return redirect(url_for("login_user"))
    depots = Depot.query.filter_by(user_id=session["user_id"]).all()
    return render_template("historique_depots.html", depots=depots)

@app.route("/historique_retraits")
def historique_retraits():
    if "user_id" not in session:
        return redirect(url_for("login_user"))
    retraits = Retrait.query.filter_by(user_id=session["user_id"]).all()
    return render_template("historique_retraits.html", retraits=retraits)

# --- ESPACE ADMINISTRATEUR ---
@app.route("/admin")
def admin_panel():
    if session.get("telephone") != "kosmaRoukaya":
        return redirect(url_for("login_user"))

    depots = (
        db.session.query(Depot, Utilisateur)
        .join(Utilisateur, Depot.user_id == Utilisateur.id)
        .filter(Depot.statut == "En attente")
        .all()
    )
    retraits = (
        db.session.query(Retrait, Utilisateur)
        .join(Utilisateur, Retrait.user_id == Utilisateur.id)
        .filter(Retrait.statut == "En attente")
        .all()
    )
    investisseurs = Utilisateur.query.all()

    return render_template(
        "admin.html", depots=depots, retraits=retraits, investisseurs=investisseurs
    )

@app.route("/admin/valider_depot/<int:id>", methods=["POST"])
def valider_depot(id):
    if session.get("telephone") != "kosmaRoukaya":
        return redirect(url_for("login_user"))

    depot = db.session.get(Depot, id)
    user = db.session.get(Utilisateur, depot.user_id)

    user.solde += depot.montant
    user.total_recharge += depot.montant

    if user.est_premier_depot:
        user.solde += 1000
        user.est_premier_depot = False

    if user.parrain_id:
        parrain = db.session.get(Utilisateur, user.parrain_id)
        if parrain:
            parrain.solde += depot.montant * 0.15

    depot.statut = "Validé"
    db.session.commit()
    return redirect(url_for("admin_panel"))

@app.route("/admin/valider_retrait/<int:id>", methods=["POST"])
def valider_retrait(id):
    if session.get("telephone") != "kosmaRoukaya":
        return redirect(url_for("login_user"))

    retrait = db.session.get(Retrait, id)
    user = db.session.get(Utilisateur, retrait.user_id)

    user.total_retrait += retrait.montant
    retrait.statut = "Validé"
    db.session.commit()
    return redirect(url_for("admin_panel"))

@app.route("/admin/bloquer_utilisateur/<int:id>", methods=["POST"])
def bloquer_utilisateur(id):
    if session.get("telephone") != "kosmaRoukaya":
        return redirect(url_for("login_user"))

    user = db.session.get(Utilisateur, id)
    if user:
        user.est_bloque = not user.est_bloque
        db.session.commit()
    return redirect(url_for("admin_panel"))

with app.app_context():
    db.create_all()

if __name__ == "__main__":
    app.run(debug=True)
  
