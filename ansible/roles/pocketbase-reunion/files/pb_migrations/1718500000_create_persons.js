/// <reference path="../pb_data/types.d.ts" />
migrate((db) => {
  const dao = new Dao(db);
  const users = dao.findCollectionByNameOrId("users");
  const RULE = "@request.auth.id != \"\" && @request.auth.approved = true";

  const collection = new Collection({
    name: "persons",
    type: "base",
    listRule: RULE,
    viewRule: RULE,
    createRule: RULE,
    updateRule: RULE,
    deleteRule: RULE,
    schema: [
      { name: "display_name", type: "text", required: true },
      { name: "given_name",  type: "text" },
      { name: "family_name", type: "text" },
      { name: "gender", type: "select",
        options: { maxSelect: 1, values: ["male", "female", "other", "unknown"] } },
      { name: "birth_date", type: "text" },
      { name: "death_date", type: "text" },
      { name: "living", type: "bool" },
      { name: "bio", type: "text" },
      { name: "photo", type: "file",
        options: { maxSelect: 1, maxSize: 5242880,
          mimeTypes: ["image/jpeg", "image/png", "image/webp", "image/gif"] } },
      { name: "linked_user", type: "relation",
        options: { collectionId: users.id, maxSelect: 1, cascadeDelete: false } },
      { name: "created_by", type: "relation",
        options: { collectionId: users.id, maxSelect: 1, cascadeDelete: false } },
      { name: "updated_by", type: "relation",
        options: { collectionId: users.id, maxSelect: 1, cascadeDelete: false } },
      { name: "gedcom_id", type: "text" }
    ]
  });

  dao.saveCollection(collection);

  // Self-referential relations require the collection's own id (set after first save).
  collection.schema.addField(new SchemaField({
    name: "father", type: "relation",
    options: { collectionId: collection.id, maxSelect: 1, cascadeDelete: false }
  }));
  collection.schema.addField(new SchemaField({
    name: "mother", type: "relation",
    options: { collectionId: collection.id, maxSelect: 1, cascadeDelete: false }
  }));
  return dao.saveCollection(collection);
}, (db) => {
  const dao = new Dao(db);
  return dao.deleteCollection(dao.findCollectionByNameOrId("persons"));
});
