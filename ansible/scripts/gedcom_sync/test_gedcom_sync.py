from gedcom_sync import (
    parse_lines, parse_individual, parse_family,
    apply_privacy, fill_blanks, plan_person_write,
)


# ── parse_lines ──────────────────────────────────────────────────────────────
def test_parse_lines_splits_level_tag_value():
    text = "0 @I1@ INDI\n1 NAME John /Smith/\n1 SEX M\n1 BIRT\n2 DATE 3 MAR 1947"
    assert parse_lines(text) == [
        (0, "INDI", "@I1@"),
        (1, "NAME", "John /Smith/"),
        (1, "SEX", "M"),
        (1, "BIRT", ""),
        (2, "DATE", "3 MAR 1947"),
    ]


# ── parse_individual ─────────────────────────────────────────────────────────
def test_parse_individual_full():
    text = ("0 @I1@ INDI\n1 NAME John /Smith/\n1 SEX M\n"
            "1 BIRT\n2 DATE 3 MAR 1947\n1 DEAT\n2 DATE 2020")
    p = parse_individual(text)
    assert p == {
        "given_name": "John", "family_name": "Smith",
        "display_name": "John Smith", "gender": "male",
        "birth_date": "1947-03-03", "death_date": "2020",
    }


def test_parse_individual_living_no_death():
    text = "0 @I2@ INDI\n1 NAME Jane /Doe/\n1 SEX F\n1 BIRT\n2 DATE 1990"
    p = parse_individual(text)
    assert p["gender"] == "female"
    assert p["birth_date"] == "1990"
    assert "death_date" not in p


def test_parse_individual_partial_name_only():
    p = parse_individual("0 @I3@ INDI\n1 NAME Madonna")
    assert p["display_name"] == "Madonna"
    assert p["given_name"] == "Madonna"
    assert p["family_name"] == ""
    assert p["gender"] == "unknown"


# ── parse_family ─────────────────────────────────────────────────────────────
def test_parse_family_full():
    text = ("0 @F1@ FAM\n1 HUSB @I1@\n1 WIFE @I2@\n1 CHIL @I3@\n1 CHIL @I4@\n"
            "1 MARR\n2 DATE 12 JUN 1970")
    f = parse_family(text)
    assert f == {"husb": "@I1@", "wife": "@I2@",
                 "children": ["@I3@", "@I4@"], "married_date": "1970-06-12"}


def test_parse_family_single_parent_no_marr():
    f = parse_family("0 @F2@ FAM\n1 WIFE @I9@\n1 CHIL @I10@")
    assert f == {"husb": "", "wife": "@I9@",
                 "children": ["@I10@"], "married_date": ""}


# ── apply_privacy ────────────────────────────────────────────────────────────
def test_apply_privacy_redacts_living():
    fields = {"display_name": "Jane Doe", "given_name": "Jane",
              "birth_date": "1990", "bio": "secret"}
    out = apply_privacy(dict(fields), now_year=2026)
    assert out["living"] is True
    assert out["birth_date"] == ""
    assert out.get("bio", "") == ""
    assert out["display_name"] == "Jane Doe"


def test_apply_privacy_deceased_kept():
    fields = {"display_name": "John Smith", "birth_date": "1947-03-03",
              "death_date": "2020"}
    out = apply_privacy(dict(fields), now_year=2026)
    assert out["living"] is False
    assert out["birth_date"] == "1947-03-03"


def test_apply_privacy_old_birth_not_living():
    fields = {"display_name": "Old One", "birth_date": "1900"}
    out = apply_privacy(dict(fields), now_year=2026)
    assert out["living"] is False
    assert out["birth_date"] == "1900"


# ── fill_blanks ──────────────────────────────────────────────────────────────
def test_fill_blanks_only_fills_empty_existing_fields():
    existing = {"display_name": "Jane D", "birth_date": "1991", "bio": ""}
    incoming = {"display_name": "Jane Doe", "birth_date": "1990",
                "bio": "from gedcom", "gender": "female"}
    patch = fill_blanks(existing, incoming)
    assert patch == {"bio": "from gedcom", "gender": "female"}


def test_fill_blanks_empty_existing_dict_takes_all():
    patch = fill_blanks({}, {"display_name": "X", "gender": "male"})
    assert patch == {"display_name": "X", "gender": "male"}


# ── plan_person_write ────────────────────────────────────────────────────────
def test_plan_person_write_new():
    action, fields = plan_person_write(None, "@I1@",
        {"display_name": "John Smith", "given_name": "John", "family_name": "Smith",
         "gender": "male", "birth_date": "1947", "living": False})
    assert action == "create"
    assert fields["gedcom_id"] == "@I1@"
    assert fields["display_name"] == "John Smith"


def test_plan_person_write_existing_fill_blanks():
    existing = {"id": "abc", "display_name": "John S", "given_name": "John",
                "family_name": "", "gender": "unknown", "birth_date": "1947",
                "living": False, "bio": ""}
    action, fields = plan_person_write(existing, "@I1@",
        {"display_name": "John Smith", "given_name": "John", "family_name": "Smith",
         "gender": "male", "birth_date": "1947", "living": False})
    assert action == "update"
    assert fields == {"family_name": "Smith", "gender": "male"}


def test_plan_person_write_existing_nothing_to_do():
    existing = {"id": "abc", "display_name": "John Smith", "given_name": "John",
                "family_name": "Smith", "gender": "male", "birth_date": "1947",
                "living": False, "bio": "x"}
    action, fields = plan_person_write(existing, "@I1@",
        {"display_name": "John Smith", "given_name": "John", "family_name": "Smith",
         "gender": "male", "birth_date": "1947", "living": False})
    assert action == "noop"
    assert fields == {}
