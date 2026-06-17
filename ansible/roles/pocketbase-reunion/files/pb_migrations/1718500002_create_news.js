/// <reference path="../pb_data/types.d.ts" />
// Restores the portal's `news` collection as reproducible schema-as-code.
// (Originally created by hand; lost when the pb_data mount-path bug reset the DB.)
migrate((db) => {
  const dao = new Dao(db);
  const users = dao.findCollectionByNameOrId("users");
  const RULE = "@request.auth.id != \"\" && @request.auth.approved = true";

  const collection = new Collection({
    name: "news",
    type: "base",
    listRule: RULE,
    viewRule: RULE,
    createRule: RULE,
    updateRule: RULE,
    deleteRule: RULE,
    schema: [
      { name: "title", type: "text", required: true },
      { name: "body", type: "text", required: true },
      { name: "author", type: "relation",
        options: { collectionId: users.id, maxSelect: 1, cascadeDelete: false } }
    ]
  });
  return dao.saveCollection(collection);
}, (db) => {
  const dao = new Dao(db);
  return dao.deleteCollection(dao.findCollectionByNameOrId("news"));
});
