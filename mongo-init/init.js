db = db.getSiblingDB('labnet');

db.createUser({
  user: "labjarkom01",
  pwd: "labjarkom01",
  roles: [{ role: "readWrite", db: "labnet" }]
});
