"""
MKJ SUPA CUP Teams - Service Layer
Higher-level business operations that span multiple model interactions.
"""


def promote_to_subcounty(ward_player, target_sub_county, created_by=None):
    """Promote a ward-level CountyPlayer to sub-county level.

    Creates a new CountyPlayer at level='subcounty' linked via source_ward_player.
    Identity fields are copied; verification step statuses start fresh (not copied).

    Requirements: 8.1, 8.4, 8.6
    """
    from teams.models import CountyPlayer, CountyDiscipline

    # Uniqueness check — Req 8.3
    if CountyPlayer.objects.filter(
        national_id_number=ward_player.national_id_number,
        discipline__level='subcounty',
        discipline__sub_county=target_sub_county,
    ).exists():
        raise ValueError(
            f'A player with national ID {ward_player.national_id_number} '
            f'already exists at sub-county level in {target_sub_county}.'
        )

    # Find or create the sub-county discipline
    discipline, _ = CountyDiscipline.objects.get_or_create(
        sport_type=ward_player.discipline.sport_type,
        sub_county=target_sub_county,
        level='subcounty',
        registration=ward_player.discipline.registration,
        defaults={
            'ward': '',
        },
    )

    # Create new CountyPlayer at subcounty level — copy identity fields only
    subcounty_player = CountyPlayer.objects.create(
        discipline=discipline,
        first_name=ward_player.first_name,
        last_name=ward_player.last_name,
        date_of_birth=ward_player.date_of_birth,
        national_id_number=ward_player.national_id_number,
        phone=ward_player.phone or '',
        position=ward_player.position or '',
        ward=ward_player.ward or '',
        sub_county=target_sub_county,
        photo=ward_player.photo or None,
        id_document=ward_player.id_document or None,
        birth_certificate=ward_player.birth_certificate or None,
        huduma_number=ward_player.huduma_number or '',
        source_ward_player=ward_player,
        # Fresh verification required at sub-county level — do NOT copy step statuses
        doc_status='not_checked',
        iprs_age_status='not_checked',
        huduma_status='not_checked',
        higher_league_status='not_checked',
        verification_status='pending',
    )
    return subcounty_player


def promote_to_county(subcounty_player, created_by=None):
    """Promote a sub-county-level CountyPlayer to county level.

    Creates a new CountyPlayer at level='county'. Identity fields and completed
    verification step statuses are carried forward (Req 7.3, 8.2, 8.5).
    The overall verification_status is reset to 'pending' pending
    a final countersignature at county level.

    Requirements: 8.2, 8.5, 7.3
    """
    from teams.models import CountyPlayer, CountyDiscipline

    # Uniqueness check — Req 8.3
    if CountyPlayer.objects.filter(
        national_id_number=subcounty_player.national_id_number,
        discipline__level='county',
    ).exists():
        raise ValueError(
            f'A player with national ID {subcounty_player.national_id_number} '
            f'already exists at county level.'
        )

    # Find county discipline (level=county, same sport_type)
    county_discipline = CountyDiscipline.objects.filter(
        level='county',
        sport_type=subcounty_player.discipline.sport_type,
    ).first()
    if not county_discipline:
        raise ValueError(
            f'No county-level discipline found for {subcounty_player.discipline.sport_type}.'
        )

    # Create county player — copy identity + pre-fill verification steps (Req 7.3, 8.5)
    county_player = CountyPlayer.objects.create(
        discipline=county_discipline,
        first_name=subcounty_player.first_name,
        last_name=subcounty_player.last_name,
        date_of_birth=subcounty_player.date_of_birth,
        national_id_number=subcounty_player.national_id_number,
        phone=subcounty_player.phone or '',
        position=subcounty_player.position or '',
        ward=subcounty_player.ward or '',
        sub_county=subcounty_player.sub_county or '',
        photo=subcounty_player.photo or None,
        id_document=subcounty_player.id_document or None,
        birth_certificate=subcounty_player.birth_certificate or None,
        huduma_number=subcounty_player.huduma_number or '',
        source_subcounty_player=subcounty_player,
        # Carry forward verification step statuses (Req 7.3, 8.2)
        doc_status=subcounty_player.doc_status,
        doc_verified_at=subcounty_player.doc_verified_at,
        doc_rejection_reason=subcounty_player.doc_rejection_reason or '',
        iprs_age_status=subcounty_player.iprs_age_status,
        iprs_age_verified_at=subcounty_player.iprs_age_verified_at,
        iprs_age_notes=subcounty_player.iprs_age_notes or '',
        huduma_status=subcounty_player.huduma_status,
        huduma_verified_at=subcounty_player.huduma_verified_at,
        higher_league_status=subcounty_player.higher_league_status,
        higher_league_checked_at=subcounty_player.higher_league_checked_at,
        higher_league_details=subcounty_player.higher_league_details or '',
        # Requires final countersignature at county level
        verification_status='pending',
    )
    return county_player
