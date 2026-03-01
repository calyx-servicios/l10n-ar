import logging

_logger = logging.getLogger(__name__)

TAG_MAPPING = {
    'tag_tax_jurisdiccion_901': 'Jur: 901 - Capital Federal',
    'tag_tax_jurisdiccion_902': 'Jur: 902 - Buenos Aires',
    'tag_tax_jurisdiccion_903': 'Jur: 903 - Catamarca',
    'tag_tax_jurisdiccion_904': 'Jur: 904 - Córdoba',
    'tag_tax_jurisdiccion_905': 'Jur: 905 - Corrientes',
    'tag_tax_jurisdiccion_906': 'Jur: 906 - Chaco',
    'tag_tax_jurisdiccion_907': 'Jur: 907 - Chubut',
    'tag_tax_jurisdiccion_908': 'Jur: 908 - Entre Ríos',
    'tag_tax_jurisdiccion_909': 'Jur: 909 - Formosa',
    'tag_tax_jurisdiccion_910': 'Jur: 910 - Jujuy',
    'tag_tax_jurisdiccion_911': 'Jur: 911 - La Pampa',
    'tag_tax_jurisdiccion_912': 'Jur: 912 - La Rioja',
    'tag_tax_jurisdiccion_913': 'Jur: 913 - Mendoza',
    'tag_tax_jurisdiccion_914': 'Jur: 914 - Misiones',
    'tag_tax_jurisdiccion_915': 'Jur: 915 - Neuquén',
    'tag_tax_jurisdiccion_916': 'Jur: 916 - Río Negro',
    'tag_tax_jurisdiccion_917': 'Jur: 917 - Salta',
    'tag_tax_jurisdiccion_918': 'Jur: 918 - San Juan',
    'tag_tax_jurisdiccion_919': 'Jur: 919 - San Luis',
    'tag_tax_jurisdiccion_920': 'Jur: 920 - Santa Cruz',
    'tag_tax_jurisdiccion_921': 'Jur: 921 - Santa Fe',
    'tag_tax_jurisdiccion_922': 'Jur: 922 - Santiago del Estero',
    'tag_tax_jurisdiccion_923': 'Jur: 923 - Tierra del Fuego',
    'tag_tax_jurisdiccion_924': 'Jur: 924 - Tucumán',
}

MODULE_NAME = 'l10n_ar_perception_automatic'


def pre_init_hook(env):
    """Link existing account.account.tag records to XML IDs so the
    data XML doesn't try to re-create them and hit the unique constraint."""
    cr = env.cr
    for xml_id, tag_name in TAG_MAPPING.items():
        cr.execute("""
            SELECT id FROM account_account_tag
            WHERE EXISTS (
                SELECT 1 FROM jsonb_each_text(name) jt WHERE jt.value = %s
            )
              AND applicability = 'taxes'
              AND country_id = (SELECT id FROM res_country WHERE code = 'AR' LIMIT 1)
            LIMIT 1
        """, (tag_name,))
        row = cr.fetchone()
        if not row:
            continue
        tag_id = row[0]
        cr.execute("""
            SELECT id FROM ir_model_data
            WHERE module = %s AND name = %s
        """, (MODULE_NAME, xml_id))
        if cr.fetchone():
            continue
        _logger.info("Linking existing tag '%s' (id=%s) to XML ID %s.%s",
                     tag_name, tag_id, MODULE_NAME, xml_id)
        cr.execute("""
            INSERT INTO ir_model_data (module, name, model, res_id, noupdate)
            VALUES (%s, %s, 'account.account.tag', %s, false)
        """, (MODULE_NAME, xml_id, tag_id))
