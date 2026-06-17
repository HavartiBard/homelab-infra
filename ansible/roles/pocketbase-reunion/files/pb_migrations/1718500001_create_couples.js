/// <reference path="../pb_data/types.d.ts" />
migrate((db) => {
  const dao = new Dao(db);
  const users = dao.findCollectionByNameOrId("users");
  const persons = dao.findCollectionByNameOrId("persons");
  const RULE = "@request.auth.id != \"\" && @request.auth.approved = true";

  const collection = new Collection({
    name: "couples",
    type: "base",
    listRule: RULE,
    viewRule: RULE,
    createRule: RULE,
    updateRule: RULE,
    deleteRule: RULE,
    schema: [
      { name: "partner_a", type: "relation", required: true,
        options: { collectionId: persons.id, maxSelect: 1, cascadeDelete: false } },
      { name: "partner_b", type: "relation", required: true,
        options: { collectionId: persons.id, maxSelect: 1, cascadeDelete: false } },
      { name: "status", type: "select",
        options: { maxSelect: 1, values: ["married", "divorced", "partners", "unknown"] } },
      { name: "married_date", type: "text" },
      { name: "created_by", type: "relation",
        options: { collectionId: users.id, maxSelect: 1, cascadeDelete: false } },
      { name: "updated_by", type: "relation",
        options: { collectionId: users.id, maxSelect: 1, cascadeDelete: false } }
    ]
  });
  return dao.saveCollection(collection);
}, (db) => {
  const dao = new Dao(db);
  return dao.deleteCollection(dao.findCollectionByNameOrId("couples"));
});
