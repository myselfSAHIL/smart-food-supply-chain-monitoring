"""
app.py
------
Flask website for the Smart Food Supply Chain Monitoring course project.

Run with:
    python app.py

Then open http://127.0.0.1:5000 in a browser.
"""

import io
import base64

import qrcode
from flask import Flask, render_template, request, redirect, url_for, flash, jsonify

from blockchain import Blockchain

app = Flask(__name__)
app.secret_key = "course-project-demo-secret"  # fine for a local course-project demo

bc = Blockchain()

ROLES = ["Producer", "Transporter", "Warehouse", "Retailer", "Regulator"]
STAGES = ["Processing", "Packaging", "Transportation", "Storage", "Retail"]


def make_qr_base64(data_url):
    """Generate a QR code PNG (as base64) that points to the consumer verify page."""
    qr = qrcode.QRCode(box_size=6, border=2)
    qr.add_data(data_url)
    qr.make(fit=True)
    img = qr.make_image(fill_color="black", back_color="white")
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return base64.b64encode(buf.getvalue()).decode()


@app.route("/")
def index():
    batches = bc.get_all_batches()
    valid, msg = bc.is_chain_valid()
    return render_template(
        "index.html",
        batches=batches,
        chain_valid=valid,
        chain_message=msg,
        alerts=bc.get_recent_alerts(5),
    )


@app.route("/register", methods=["POST"])
def register():
    producer = request.form["producer"].strip()
    product_name = request.form["product_name"].strip()
    origin = request.form["origin"].strip()
    batch_id, _ = bc.register_product(producer, product_name, origin)
    flash(f"Product registered on-chain. Batch ID: {batch_id}", "success")
    return redirect(url_for("product_detail", batch_id=batch_id))


@app.route("/product/<batch_id>")
def product_detail(batch_id):
    history = bc.verify_provenance(batch_id)
    if not history:
        flash("Batch not found.", "error")
        return redirect(url_for("index"))
    verify_url = url_for("verify", batch_id=batch_id, _external=True)
    qr_b64 = make_qr_base64(verify_url)
    return render_template(
        "product_detail.html",
        batch_id=batch_id,
        history=history,
        roles=ROLES,
        stages=STAGES,
        qr_b64=qr_b64,
        verify_url=verify_url,
    )


@app.route("/event/<batch_id>", methods=["POST"])
def add_event(batch_id):
    stage = request.form["stage"]
    location = request.form["location"].strip()
    handler = request.form["handler"].strip()
    actor_role = request.form["actor_role"]
    bc.add_event(batch_id, stage, location, handler, actor_role)
    flash(f"Event '{stage}' recorded on-chain for {batch_id}.", "success")
    return redirect(url_for("product_detail", batch_id=batch_id))


@app.route("/sensor/<batch_id>", methods=["POST"])
def add_sensor(batch_id):
    temperature = float(request.form["temperature"])
    humidity = float(request.form["humidity"])
    location = request.form["location"].strip()
    _, violations, _ = bc.record_sensor_reading(batch_id, temperature, humidity, location)
    if violations:
        flash(f"Sensor reading recorded. ALERT triggered: {', '.join(violations)}", "error")
    else:
        flash("Sensor reading recorded on-chain. Conditions normal.", "success")
    return redirect(url_for("product_detail", batch_id=batch_id))


@app.route("/transfer/<batch_id>", methods=["POST"])
def transfer(batch_id):
    new_owner = request.form["new_owner"].strip()
    actor_role = request.form["actor_role"]
    bc.transfer_ownership(batch_id, new_owner, actor_role)
    flash(f"Ownership transferred to {new_owner}.", "success")
    return redirect(url_for("product_detail", batch_id=batch_id))


@app.route("/verify/<batch_id>")
def verify(batch_id):
    """Public, read-only page -- this is what the consumer lands on after
    scanning the QR code printed on the product."""
    history = bc.verify_provenance(batch_id)
    return render_template("verify.html", batch_id=batch_id, history=history)


@app.route("/chain")
def chain_view():
    valid, msg = bc.is_chain_valid()
    return render_template(
        "chain.html",
        chain=[b.to_dict() for b in bc.get_all_blocks()],
        valid=valid,
        message=msg,
    )


# Simple JSON API -- handy if you want to simulate an IoT device posting
# sensor readings with curl/Postman instead of the form.
@app.route("/api/verify/<batch_id>")
def api_verify(batch_id):
    return jsonify(bc.verify_provenance(batch_id))


@app.route("/api/sensor/<batch_id>", methods=["POST"])
def api_sensor(batch_id):
    payload = request.get_json(force=True)
    _, violations, _ = bc.record_sensor_reading(
        batch_id, float(payload["temperature"]), float(payload["humidity"]),
        payload.get("location", "IoT Sensor")
    )
    return jsonify({"batch_id": batch_id, "violations": violations})


if __name__ == "__main__":
    app.run(debug=True, port=5000)
