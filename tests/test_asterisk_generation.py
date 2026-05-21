from pathlib import Path

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.config import Settings
from app.database import Base
from app.models import Extension, InboundRoute, IvrMenu, IvrOption, OutboundRule, RingGroup, RingGroupMember, SipTrunk
from app.services.asterisk import apply_revision, generate_config, render_configs


def test_render_minimal_pjsip_and_dialplan(tmp_path: Path):
    engine = create_engine(f"sqlite:///{tmp_path / 'test.db'}", connect_args={"check_same_thread": False})
    Base.metadata.create_all(engine)
    session = sessionmaker(bind=engine)()
    session.add(
        Extension(
            number="101",
            display_name="Accueil",
            sip_username="101",
            sip_secret="secret",
            voicemail_enabled=True,
            voicemail_pin="0101",
            outbound_enabled=True,
            inbound_enabled=True,
            enabled=True,
        )
    )
    session.commit()

    settings = Settings(
        secret_key="test",
        data_dir=tmp_path,
        generated_config_dir=tmp_path / "generated",
        backup_dir=tmp_path / "backups",
        asterisk_config_dir=tmp_path / "asterisk",
        asterisk_apply_enabled=False,
        tts_backend="none",
    )
    configs = render_configs(session, settings)

    assert "pjsip_minipbx.conf" in configs
    assert "[101]" in configs["pjsip_minipbx.conf"]
    assert "password=secret" in configs["pjsip_minipbx.conf"]
    assert "exten => 101,1,Dial(PJSIP/101,20)" in configs["extensions_minipbx.conf"]
    assert "manager_minipbx.conf" in configs
    assert "[minipbx]" in configs["manager_minipbx.conf"]
    assert "bindaddr=127.0.0.1" in configs["manager_minipbx.conf"]
    assert "permit=127.0.0.1/255.255.255.255" in configs["manager_minipbx.conf"]


def test_render_voicemail_recorded_greeting(tmp_path: Path):
    greeting_path = tmp_path / "prompts" / "voicemail.wav"
    session_engine = create_engine(f"sqlite:///{tmp_path / 'test.db'}", connect_args={"check_same_thread": False})
    Base.metadata.create_all(session_engine)
    session = sessionmaker(bind=session_engine)()
    session.add(
        Extension(
            number="101",
            display_name="Accueil",
            sip_username="101",
            sip_secret="secret",
            voicemail_enabled=True,
            voicemail_pin="0101",
            voicemail_greeting_mode="recording",
            voicemail_greeting_audio_path=str(greeting_path),
            outbound_enabled=True,
            inbound_enabled=True,
            enabled=True,
        )
    )
    session.commit()
    settings = Settings(
        secret_key="test",
        data_dir=tmp_path,
        generated_config_dir=tmp_path / "generated",
        backup_dir=tmp_path / "backups",
        asterisk_config_dir=tmp_path / "asterisk",
        asterisk_apply_enabled=False,
    )

    dialplan = render_configs(session, settings)["extensions_minipbx.conf"]

    assert "same => n,Goto(minipbx-voicemail,101,1)" in dialplan
    assert "[minipbx-voicemail]" in dialplan
    assert f"Background({greeting_path.with_suffix('')})" in dialplan
    assert "VoiceMail(101@default,s)" in dialplan


def test_render_voicemail_tts_greeting_when_flite_enabled(tmp_path: Path):
    session_engine = create_engine(f"sqlite:///{tmp_path / 'test.db'}", connect_args={"check_same_thread": False})
    Base.metadata.create_all(session_engine)
    session = sessionmaker(bind=session_engine)()
    session.add(
        Extension(
            number="101",
            display_name="Accueil",
            sip_username="101",
            sip_secret="secret",
            voicemail_enabled=True,
            voicemail_pin="0101",
            voicemail_greeting_mode="tts",
            voicemail_greeting_text="Laissez un message",
            outbound_enabled=True,
            inbound_enabled=True,
            enabled=True,
        )
    )
    session.commit()
    settings = Settings(
        secret_key="test",
        data_dir=tmp_path,
        generated_config_dir=tmp_path / "generated",
        backup_dir=tmp_path / "backups",
        asterisk_config_dir=tmp_path / "asterisk",
        asterisk_apply_enabled=False,
        tts_backend="flite",
    )

    dialplan = render_configs(session, settings)["extensions_minipbx.conf"]

    assert 'TryExec(Flite("Laissez un message"))' in dialplan
    assert "VoiceMail(101@default,s)" in dialplan


def test_generate_config_writes_revision(tmp_path: Path):
    engine = create_engine(f"sqlite:///{tmp_path / 'test.db'}", connect_args={"check_same_thread": False})
    Base.metadata.create_all(engine)
    session = sessionmaker(bind=engine)()
    settings = Settings(
        secret_key="test",
        data_dir=tmp_path,
        generated_config_dir=tmp_path / "generated",
        backup_dir=tmp_path / "backups",
        asterisk_config_dir=tmp_path / "asterisk",
        asterisk_apply_enabled=False,
    )

    revision = generate_config(session, settings)

    assert revision.status == "generated"
    assert (Path(revision.generated_path) / "pjsip_minipbx.conf").exists()


def test_apply_revision_can_write_without_reload(tmp_path: Path):
    engine = create_engine(f"sqlite:///{tmp_path / 'test.db'}", connect_args={"check_same_thread": False})
    Base.metadata.create_all(engine)
    session = sessionmaker(bind=engine)()
    settings = Settings(
        secret_key="test",
        data_dir=tmp_path,
        generated_config_dir=tmp_path / "generated",
        backup_dir=tmp_path / "backups",
        asterisk_config_dir=tmp_path / "asterisk",
        asterisk_apply_enabled=True,
        asterisk_reload_command="false",
    )

    revision = generate_config(session, settings)
    applied = apply_revision(session, revision, settings, reload_asterisk=False)

    assert applied.status == "applied"
    assert "avant demarrage Asterisk" in applied.summary
    assert (settings.asterisk_config_dir / "extensions_minipbx.conf").exists()


def test_apply_revision_restores_previous_files_when_reload_fails(tmp_path: Path):
    engine = create_engine(f"sqlite:///{tmp_path / 'test.db'}", connect_args={"check_same_thread": False})
    Base.metadata.create_all(engine)
    session = sessionmaker(bind=engine)()
    settings = Settings(
        secret_key="test",
        data_dir=tmp_path,
        generated_config_dir=tmp_path / "generated",
        backup_dir=tmp_path / "backups",
        asterisk_config_dir=tmp_path / "asterisk",
        asterisk_apply_enabled=True,
        asterisk_reload_command="false",
    )
    settings.asterisk_config_dir.mkdir(parents=True)
    previous = "; previous config\n"
    (settings.asterisk_config_dir / "pjsip_minipbx.conf").write_text(previous, encoding="utf-8")

    revision = generate_config(session, settings)
    applied = apply_revision(session, revision, settings)

    assert applied.status == "reload_failed"
    assert "ancienne configuration restauree" in applied.summary
    assert (settings.asterisk_config_dir / "pjsip_minipbx.conf").read_text(encoding="utf-8") == previous


def test_render_ring_group_and_inbound_route(tmp_path: Path):
    engine = create_engine(f"sqlite:///{tmp_path / 'test.db'}", connect_args={"check_same_thread": False})
    Base.metadata.create_all(engine)
    session = sessionmaker(bind=engine)()
    first = Extension(
        number="100",
        display_name="Poste 100",
        sip_username="100",
        sip_secret="secret-100",
        voicemail_enabled=True,
        voicemail_pin="0100",
        outbound_enabled=True,
        inbound_enabled=True,
        enabled=True,
    )
    second = Extension(
        number="101",
        display_name="Poste 101",
        sip_username="101",
        sip_secret="secret-101",
        voicemail_enabled=True,
        voicemail_pin="0101",
        outbound_enabled=True,
        inbound_enabled=True,
        enabled=True,
    )
    session.add_all([first, second])
    session.flush()
    group = RingGroup(
        name="Accueil",
        number="600",
        timeout_seconds=20,
        fallback_type="voicemail",
        fallback_target="100",
    )
    group.members = [RingGroupMember(extension_id=first.id), RingGroupMember(extension_id=second.id)]
    session.add(group)
    session.add(
        InboundRoute(
            name="Route entrante principale",
            open_destination_type="ring_group",
            open_destination_target="600",
            closed_destination_type="hangup",
        )
    )
    session.commit()

    settings = Settings(
        secret_key="test",
        data_dir=tmp_path,
        generated_config_dir=tmp_path / "generated",
        backup_dir=tmp_path / "backups",
        asterisk_config_dir=tmp_path / "asterisk",
        asterisk_apply_enabled=False,
    )
    configs = render_configs(session, settings)

    dialplan = configs["extensions_minipbx.conf"]
    assert "exten => 600,1,NoOp(Ring group Accueil)" in dialplan
    assert "Dial(PJSIP/100&PJSIP/101,20)" in dialplan
    assert "NoOp(Ring group 600 ended with DIALSTATUS=${DIALSTATUS})" in dialplan
    assert "Goto(minipbx-internal,600,1)" in dialplan
    assert "Goto(minipbx-voicemail,100,1)" in dialplan


def test_render_outbound_rules_with_prefix_and_international_block(tmp_path: Path):
    engine = create_engine(f"sqlite:///{tmp_path / 'test.db'}", connect_args={"check_same_thread": False})
    Base.metadata.create_all(engine)
    session = sessionmaker(bind=engine)()
    session.add(
        Extension(
            number="100",
            display_name="Poste 100",
            sip_username="100",
            sip_secret="secret-100",
            voicemail_enabled=True,
            voicemail_pin="0100",
            outbound_enabled=True,
            inbound_enabled=True,
            enabled=True,
        )
    )
    session.add(
        SipTrunk(
            name="Trunk",
            host="sip.example.test",
            username="account",
            password_secret="secret",
            transport="udp",
            enabled=True,
        )
    )
    session.add(
        OutboundRule(
            name="Sortant",
            prefix="9",
            allow_national=True,
            allow_mobile=True,
            allow_international=False,
            emergency_numbers="15,17,18,112",
        )
    )
    session.commit()
    settings = Settings(
        secret_key="test",
        data_dir=tmp_path,
        generated_config_dir=tmp_path / "generated",
        backup_dir=tmp_path / "backups",
        asterisk_config_dir=tmp_path / "asterisk",
        asterisk_apply_enabled=False,
    )

    dialplan = render_configs(session, settings)["extensions_minipbx.conf"]

    assert "exten => 915,1,NoOp(Emergency call 15)" in dialplan
    assert "exten => _9*21*0[1-9]XXXXXXXX,1,NoOp(Operator call forwarding activation)" in dialplan
    assert "exten => _9*21*0[1-9]XXXXXXXX#,1,NoOp(Operator call forwarding activation with terminator)" in dialplan
    assert "exten => 9*21*,1,NoOp(Interactive operator call forwarding activation)" in dialplan
    assert "exten => 9#21#,1,NoOp(Operator call forwarding deactivation)" in dialplan
    assert "exten => 9*#21#,1,NoOp(Operator call forwarding status)" in dialplan
    assert "Dial(${PJSIP_DIAL_CONTACTS(trunk-main,,*21*${EXTEN:5})},60)" in dialplan
    assert "Dial(${PJSIP_DIAL_CONTACTS(trunk-main,,trunk-main)},60,D(ww*21*${EXTEN:5:10}#))" in dialplan
    assert "Read(FWD_NUMBER,beep,10,,1,20)" in dialplan
    assert 'GotoIf($["${FWD_NUMBER}" : "^0[1-9][0-9]{8}$"]?dial:invalid)' in dialplan
    assert "Dial(${PJSIP_DIAL_CONTACTS(trunk-main,,*21*${FWD_NUMBER})},60)" in dialplan
    assert "Dial(${PJSIP_DIAL_CONTACTS(trunk-main,,trunk-main)},60,D(ww#21#))" in dialplan
    assert "Dial(${PJSIP_DIAL_CONTACTS(trunk-main,,trunk-main)},60,D(ww*#21#))" in dialplan
    assert "exten => _900X.,1,Playback(feature-not-avail-line)" in dialplan
    assert "exten => _90[67]XXXXXXXX,1,NoOp(Mobile outbound call)" in dialplan
    assert "Dial(PJSIP/${EXTEN:1}@trunk-main,60)" in dialplan


def test_render_trunk_identify_uses_inbound_match_or_host(tmp_path: Path):
    engine = create_engine(f"sqlite:///{tmp_path / 'test.db'}", connect_args={"check_same_thread": False})
    Base.metadata.create_all(engine)
    session = sessionmaker(bind=engine)()
    session.add(
        SipTrunk(
            name="FreePro",
            host="sip.freepro.com",
            username="account",
            password_secret="secret",
            from_user="0659161356",
            from_domain="sip.freepro.com",
            inbound_match="85.31.193.213\n85.31.193.214",
            transport="udp",
            enabled=True,
        )
    )
    session.commit()
    settings = Settings(
        secret_key="test",
        data_dir=tmp_path,
        generated_config_dir=tmp_path / "generated",
        backup_dir=tmp_path / "backups",
        asterisk_config_dir=tmp_path / "asterisk",
        asterisk_apply_enabled=False,
    )

    pjsip = render_configs(session, settings)["pjsip_minipbx.conf"]

    assert "[trunk-main-identify]" in pjsip
    assert "type=identify" in pjsip
    assert "endpoint=trunk-main" in pjsip
    assert "match=85.31.193.213" in pjsip
    assert "match=85.31.193.214" in pjsip


def test_render_analog_fxo_trunk_accepts_gateway_registration(tmp_path: Path):
    engine = create_engine(f"sqlite:///{tmp_path / 'test.db'}", connect_args={"check_same_thread": False})
    Base.metadata.create_all(engine)
    session = sessionmaker(bind=engine)()
    session.add(
        SipTrunk(
            name="HT813",
            kind="analog_fxo",
            host="192.168.10.130",
            username="fxo900",
            password_secret="secret-fxo",
            inbound_match="192.168.10.130",
            transport="udp",
            enabled=True,
        )
    )
    session.commit()
    settings = Settings(
        secret_key="test",
        data_dir=tmp_path,
        generated_config_dir=tmp_path / "generated",
        backup_dir=tmp_path / "backups",
        asterisk_config_dir=tmp_path / "asterisk",
        asterisk_apply_enabled=False,
    )

    pjsip = render_configs(session, settings)["pjsip_minipbx.conf"]

    assert "[trunk-main]" in pjsip
    assert "auth=trunk-main-auth" in pjsip
    assert "username=fxo900" in pjsip
    assert "password=secret-fxo" in pjsip
    assert "max_contacts=1" in pjsip
    assert "remove_existing=yes" in pjsip
    assert "qualify_frequency=60" in pjsip
    assert "match=192.168.10.130" in pjsip
    assert "[trunk-main-registration]" not in pjsip
    assert "contact=sip:192.168.10.130" not in pjsip


def test_render_analog_fxo_outbound_uses_post_answer_dtmf(tmp_path: Path):
    engine = create_engine(f"sqlite:///{tmp_path / 'test.db'}", connect_args={"check_same_thread": False})
    Base.metadata.create_all(engine)
    session = sessionmaker(bind=engine)()
    session.add(
        Extension(
            number="100",
            display_name="Poste 100",
            sip_username="100",
            sip_secret="secret-100",
            voicemail_enabled=True,
            voicemail_pin="0100",
            outbound_enabled=True,
            inbound_enabled=True,
            enabled=True,
        )
    )
    session.add(
        SipTrunk(
            name="HT813",
            kind="analog_fxo",
            host="192.168.10.130",
            username="fxo900",
            password_secret="secret-fxo",
            inbound_match="192.168.10.130",
            transport="udp",
            enabled=True,
        )
    )
    session.add(
        OutboundRule(
            name="Sortant",
            prefix="9",
            allow_national=True,
            allow_mobile=True,
            allow_international=True,
            emergency_numbers="15,17,18,112",
        )
    )
    session.commit()
    settings = Settings(
        secret_key="test",
        data_dir=tmp_path,
        generated_config_dir=tmp_path / "generated",
        backup_dir=tmp_path / "backups",
        asterisk_config_dir=tmp_path / "asterisk",
        asterisk_apply_enabled=False,
    )

    dialplan = render_configs(session, settings)["extensions_minipbx.conf"]

    assert "Dial(${PJSIP_DIAL_CONTACTS(trunk-main,,trunk-main)},60,D(ww15))" in dialplan
    assert "Dial(${PJSIP_DIAL_CONTACTS(trunk-main,,trunk-main)},60,D(ww${EXTEN:1}))" in dialplan
    assert "Dial(PJSIP/${EXTEN:1}@trunk-main,60)" not in dialplan


def test_render_ivr_menu_and_inbound_route(tmp_path: Path):
    engine = create_engine(f"sqlite:///{tmp_path / 'test.db'}", connect_args={"check_same_thread": False})
    Base.metadata.create_all(engine)
    session = sessionmaker(bind=engine)()
    session.add(
        Extension(
            number="100",
            display_name="Accueil",
            sip_username="100",
            sip_secret="secret-100",
            voicemail_enabled=True,
            voicemail_pin="0100",
            outbound_enabled=True,
            inbound_enabled=True,
            enabled=True,
        )
    )
    session.flush()
    menu = IvrMenu(
        name="Standard",
        number="700",
        prompt_mode="tts",
        prompt_text="Bonjour, tapez 1 pour l'accueil",
        timeout_seconds=8,
        fallback_type="hangup",
        enabled=True,
    )
    menu.options = [IvrOption(digit="1", destination_type="extension", destination_target="100")]
    session.add(menu)
    session.add(
        InboundRoute(
            name="Route entrante principale",
            open_destination_type="ivr",
            open_destination_target="700",
            closed_destination_type="hangup",
        )
    )
    session.commit()
    settings = Settings(
        secret_key="test",
        data_dir=tmp_path,
        generated_config_dir=tmp_path / "generated",
        backup_dir=tmp_path / "backups",
        asterisk_config_dir=tmp_path / "asterisk",
        asterisk_apply_enabled=False,
    )

    dialplan = render_configs(session, settings)["extensions_minipbx.conf"]

    assert "exten => 700,1,Goto(minipbx-ivr-" in dialplan
    assert "Goto(minipbx-internal,700,1)" in dialplan
    assert "NoOp(TTS disabled: Bonjour, tapez 1 pour l'accueil)" in dialplan
    assert "TryExec(Flite(" not in dialplan
    assert "exten => 1,1,Goto(minipbx-internal,100,1)" in dialplan


def test_render_inbound_business_hours(tmp_path: Path):
    engine = create_engine(f"sqlite:///{tmp_path / 'test.db'}", connect_args={"check_same_thread": False})
    Base.metadata.create_all(engine)
    session = sessionmaker(bind=engine)()
    session.add_all(
        [
            Extension(
                number="100",
                display_name="Accueil",
                sip_username="100",
                sip_secret="secret-100",
                voicemail_enabled=True,
                voicemail_pin="0100",
                outbound_enabled=True,
                inbound_enabled=True,
                enabled=True,
            ),
            Extension(
                number="101",
                display_name="Astreinte",
                sip_username="101",
                sip_secret="secret-101",
                voicemail_enabled=True,
                voicemail_pin="0101",
                outbound_enabled=True,
                inbound_enabled=True,
                enabled=True,
            ),
        ]
    )
    session.add(
        InboundRoute(
            name="Route entrante principale",
            use_business_hours=True,
            business_days="mon,tue,wed,thu,fri",
            business_open_time="09:00",
            business_close_time="18:00",
            holiday_dates="2026-12-25",
            open_destination_type="extension",
            open_destination_target="100",
            closed_destination_type="voicemail",
            closed_destination_target="101",
        )
    )
    session.commit()
    settings = Settings(
        secret_key="test",
        data_dir=tmp_path,
        generated_config_dir=tmp_path / "generated",
        backup_dir=tmp_path / "backups",
        asterisk_config_dir=tmp_path / "asterisk",
        asterisk_apply_enabled=False,
    )

    dialplan = render_configs(session, settings)["extensions_minipbx.conf"]

    assert "GotoIfTime(*,*,25,dec?closed)" in dialplan
    assert "GotoIfTime(09:00-18:00,mon-fri,*,*?open)" in dialplan
    assert "same => n(open),Goto(minipbx-internal,100,1)" in dialplan
    assert "same => n(closed),Goto(minipbx-voicemail,101,1)" in dialplan


def test_render_external_number_destinations_use_trunk(tmp_path: Path):
    engine = create_engine(f"sqlite:///{tmp_path / 'test.db'}", connect_args={"check_same_thread": False})
    Base.metadata.create_all(engine)
    session = sessionmaker(bind=engine)()
    extension = Extension(
        number="100",
        display_name="Accueil",
        sip_username="100",
        sip_secret="secret-100",
        voicemail_enabled=True,
        voicemail_pin="0100",
        outbound_enabled=True,
        inbound_enabled=True,
        enabled=True,
    )
    session.add(extension)
    session.flush()
    group = RingGroup(
        name="Commercial",
        number="650",
        timeout_seconds=10,
        fallback_type="external_number",
        fallback_target="0612345678",
    )
    group.members = [RingGroupMember(extension_id=extension.id)]
    menu = IvrMenu(
        name="Standard",
        number="700",
        prompt_mode="tts",
        prompt_text="Tapez 1",
        timeout_seconds=5,
        fallback_type="external_number",
        fallback_target="0622222222",
        enabled=True,
    )
    menu.options = [IvrOption(digit="1", destination_type="external_number", destination_target="0633333333")]
    session.add_all(
        [
            group,
            menu,
            InboundRoute(
                name="Renvoi commercial",
                did_number="300",
                open_destination_type="external_number",
                open_destination_target="0611111111",
                closed_destination_type="hangup",
            ),
            SipTrunk(
                name="Trunk",
                host="sip.example.test",
                username="account",
                password_secret="secret",
                transport="udp",
                enabled=True,
            ),
        ]
    )
    session.commit()
    settings = Settings(
        secret_key="test",
        data_dir=tmp_path,
        generated_config_dir=tmp_path / "generated",
        backup_dir=tmp_path / "backups",
        asterisk_config_dir=tmp_path / "asterisk",
        asterisk_apply_enabled=False,
    )

    dialplan = render_configs(session, settings)["extensions_minipbx.conf"]

    assert "Dial(PJSIP/0611111111@trunk-main,60)" in dialplan
    assert "Dial(PJSIP/0612345678@trunk-main,60)" in dialplan
    assert "Dial(PJSIP/0622222222@trunk-main,60)" in dialplan
    assert "exten => 1,1,Dial(PJSIP/0633333333@trunk-main,60)" in dialplan


def test_render_external_number_destinations_use_fxo_dtmf(tmp_path: Path):
    engine = create_engine(f"sqlite:///{tmp_path / 'test.db'}", connect_args={"check_same_thread": False})
    Base.metadata.create_all(engine)
    session = sessionmaker(bind=engine)()
    extension = Extension(
        number="100",
        display_name="Accueil",
        sip_username="100",
        sip_secret="secret-100",
        voicemail_enabled=True,
        voicemail_pin="0100",
        outbound_enabled=True,
        inbound_enabled=True,
        enabled=True,
    )
    session.add(extension)
    session.flush()
    group = RingGroup(
        name="Commercial",
        number="650",
        timeout_seconds=10,
        fallback_type="external_number",
        fallback_target="0612345678",
    )
    group.members = [RingGroupMember(extension_id=extension.id)]
    menu = IvrMenu(
        name="Standard",
        number="700",
        prompt_mode="tts",
        prompt_text="Tapez 1",
        timeout_seconds=5,
        fallback_type="external_number",
        fallback_target="0622222222",
        enabled=True,
    )
    menu.options = [IvrOption(digit="1", destination_type="external_number", destination_target="0633333333")]
    session.add_all(
        [
            group,
            menu,
            InboundRoute(
                name="Renvoi commercial",
                did_number="300",
                open_destination_type="external_number",
                open_destination_target="0611111111",
                closed_destination_type="hangup",
            ),
            SipTrunk(
                name="HT813",
                kind="analog_fxo",
                host="192.168.10.130",
                username="fxo900",
                password_secret="secret-fxo",
                inbound_match="192.168.10.130",
                transport="udp",
                enabled=True,
            ),
        ]
    )
    session.commit()
    settings = Settings(
        secret_key="test",
        data_dir=tmp_path,
        generated_config_dir=tmp_path / "generated",
        backup_dir=tmp_path / "backups",
        asterisk_config_dir=tmp_path / "asterisk",
        asterisk_apply_enabled=False,
    )

    dialplan = render_configs(session, settings)["extensions_minipbx.conf"]

    assert "Dial(${PJSIP_DIAL_CONTACTS(trunk-main,,trunk-main)},60,D(ww0611111111))" in dialplan
    assert "Dial(${PJSIP_DIAL_CONTACTS(trunk-main,,trunk-main)},60,D(ww0612345678))" in dialplan
    assert "Dial(${PJSIP_DIAL_CONTACTS(trunk-main,,trunk-main)},60,D(ww0622222222))" in dialplan
    assert "exten => 1,1,Dial(${PJSIP_DIAL_CONTACTS(trunk-main,,trunk-main)},60,D(ww0633333333))" in dialplan


def test_render_multiple_inbound_routes_by_did(tmp_path: Path):
    engine = create_engine(f"sqlite:///{tmp_path / 'test.db'}", connect_args={"check_same_thread": False})
    Base.metadata.create_all(engine)
    session = sessionmaker(bind=engine)()
    session.add_all(
        [
            Extension(
                number="100",
                display_name="Accueil",
                sip_username="100",
                sip_secret="secret-100",
                voicemail_enabled=True,
                voicemail_pin="0100",
                outbound_enabled=True,
                inbound_enabled=True,
                enabled=True,
            ),
            Extension(
                number="101",
                display_name="Support",
                sip_username="101",
                sip_secret="secret-101",
                voicemail_enabled=True,
                voicemail_pin="0101",
                outbound_enabled=True,
                inbound_enabled=True,
                enabled=True,
            ),
        ]
    )
    session.add_all(
        [
            InboundRoute(
                name="Defaut",
                open_destination_type="extension",
                open_destination_target="100",
                closed_destination_type="hangup",
            ),
            InboundRoute(
                name="Support",
                did_number="0123456789",
                open_destination_type="extension",
                open_destination_target="101",
                closed_destination_type="hangup",
            ),
        ]
    )
    session.commit()
    settings = Settings(
        secret_key="test",
        data_dir=tmp_path,
        generated_config_dir=tmp_path / "generated",
        backup_dir=tmp_path / "backups",
        asterisk_config_dir=tmp_path / "asterisk",
        asterisk_apply_enabled=False,
    )

    dialplan = render_configs(session, settings)["extensions_minipbx.conf"]

    assert "exten => s,1,Goto(minipbx-inbound-route-" in dialplan
    assert "exten => 0123456789,1,Goto(minipbx-inbound-route-" in dialplan
    assert "NoOp(Inbound route Defaut)" in dialplan
    assert "NoOp(Inbound route Support)" in dialplan
    assert "same => n,Goto(minipbx-internal,100,1)" in dialplan
    assert "same => n,Goto(minipbx-internal,101,1)" in dialplan


def test_render_ivr_menu_with_flite_backend_when_enabled(tmp_path: Path):
    engine = create_engine(f"sqlite:///{tmp_path / 'test.db'}", connect_args={"check_same_thread": False})
    Base.metadata.create_all(engine)
    session = sessionmaker(bind=engine)()
    session.add(
        Extension(
            number="100",
            display_name="Accueil",
            sip_username="100",
            sip_secret="secret-100",
            voicemail_enabled=True,
            voicemail_pin="0100",
            outbound_enabled=True,
            inbound_enabled=True,
            enabled=True,
        )
    )
    session.flush()
    menu = IvrMenu(
        name="Standard",
        number="700",
        prompt_mode="tts",
        prompt_text="Bonjour, tapez 1",
        timeout_seconds=8,
        fallback_type="hangup",
        enabled=True,
    )
    menu.options = [IvrOption(digit="1", destination_type="extension", destination_target="100")]
    session.add(menu)
    session.commit()
    settings = Settings(
        secret_key="test",
        data_dir=tmp_path,
        generated_config_dir=tmp_path / "generated",
        backup_dir=tmp_path / "backups",
        asterisk_config_dir=tmp_path / "asterisk",
        asterisk_apply_enabled=False,
        tts_backend="flite",
    )

    dialplan = render_configs(session, settings)["extensions_minipbx.conf"]

    assert "TryExec(Flite(\"Bonjour, tapez 1\"))" in dialplan


def test_render_ivr_menu_with_recorded_prompt(tmp_path: Path):
    engine = create_engine(f"sqlite:///{tmp_path / 'test.db'}", connect_args={"check_same_thread": False})
    Base.metadata.create_all(engine)
    session = sessionmaker(bind=engine)()
    session.add(
        Extension(
            number="100",
            display_name="Accueil",
            sip_username="100",
            sip_secret="secret-100",
            voicemail_enabled=True,
            voicemail_pin="0100",
            outbound_enabled=True,
            inbound_enabled=True,
            enabled=True,
        )
    )
    session.flush()
    menu = IvrMenu(
        name="Standard vocal",
        number="701",
        prompt_mode="recording",
        prompt_audio_path=str(tmp_path / "prompts" / "message.wav"),
        timeout_seconds=8,
        fallback_type="hangup",
        enabled=True,
    )
    menu.options = [IvrOption(digit="1", destination_type="extension", destination_target="100")]
    session.add(menu)
    session.commit()
    settings = Settings(
        secret_key="test",
        data_dir=tmp_path,
        generated_config_dir=tmp_path / "generated",
        backup_dir=tmp_path / "backups",
        asterisk_config_dir=tmp_path / "asterisk",
        asterisk_apply_enabled=False,
    )

    dialplan = render_configs(session, settings)["extensions_minipbx.conf"]

    assert f"Background({tmp_path / 'prompts' / 'message'})" in dialplan
