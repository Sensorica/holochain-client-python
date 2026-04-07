pub mod fixture;
pub use fixture::*;
use hdi::prelude::*;
#[hdk_entry_types]
#[unit_enum(UnitEntryTypes)]
#[derive(Serialize, Deserialize)]
pub enum EntryTypes {
    Fixture(Fixture),
}
#[hdk_link_types]
#[derive(Serialize, Deserialize)]
pub enum LinkTypes {
    FixtureUpdates,
    AllFixtures,
}
#[hdk_extern]
pub fn genesis_self_check(
    _data: GenesisSelfCheckData,
) -> ExternResult<ValidateCallbackResult> {
    Ok(ValidateCallbackResult::Valid)
}
pub fn validate_agent_joining(
    _agent_pub_key: AgentPubKey,
    _membrane_proof: &Option<MembraneProof>,
) -> ExternResult<ValidateCallbackResult> {
    Ok(ValidateCallbackResult::Valid)
}
#[hdk_extern]
pub fn validate(op: Op) -> ExternResult<ValidateCallbackResult> {
    match op.flattened::<EntryTypes, LinkTypes>()? {
        FlatOp::StoreEntry(store_entry) => {
            match store_entry {
                OpEntry::CreateEntry { app_entry, action } => {
                    match app_entry {
                        EntryTypes::Fixture(fixture) => {
                            validate_create_fixture(
                                EntryCreationAction::Create(action),
                                fixture,
                            )
                        }
                    }
                }
                OpEntry::UpdateEntry { app_entry, action, .. } => {
                    match app_entry {
                        EntryTypes::Fixture(fixture) => {
                            validate_update_fixture(action, fixture)
                        }
                    }
                }
                _ => Ok(ValidateCallbackResult::Valid),
            }
        }
        FlatOp::StoreRecord(store_record) => {
            match store_record {
                OpRecord::CreateEntry { app_entry, action } => {
                    match app_entry {
                        EntryTypes::Fixture(fixture) => {
                            validate_create_fixture(
                                EntryCreationAction::Create(action),
                                fixture,
                            )
                        }
                    }
                }
                OpRecord::UpdateEntry { app_entry, action, .. } => {
                    match app_entry {
                        EntryTypes::Fixture(fixture) => {
                            let result = validate_create_fixture(
                                EntryCreationAction::Update(action.clone()),
                                fixture.clone(),
                            )?;
                            if let ValidateCallbackResult::Valid = result {
                                validate_update_fixture(action, fixture)
                            } else {
                                Ok(result)
                            }
                        }
                    }
                }
                OpRecord::DeleteEntry { original_action_hash, action, .. } => {
                    let original_record = must_get_valid_record(original_action_hash)?;
                    let entry = match original_record.entry().as_option() {
                        Some(entry) => entry,
                        None => return Ok(ValidateCallbackResult::Valid),
                    };
                    let (zome_index, entry_index) = match original_record.action().entry_type() {
                        Some(EntryType::App(AppEntryDef { zome_index, entry_index, .. })) => {
                            (zome_index, entry_index)
                        }
                        _ => return Ok(ValidateCallbackResult::Valid),
                    };
                    match EntryTypes::deserialize_from_type(
                        zome_index.clone(),
                        entry_index.clone(),
                        entry,
                    )? {
                        Some(EntryTypes::Fixture(original_fixture)) => {
                            validate_delete_fixture(action, original_fixture)
                        }
                        _ => Ok(ValidateCallbackResult::Valid),
                    }
                }
                OpRecord::CreateLink {
                    base_address,
                    target_address,
                    tag,
                    link_type,
                    action,
                } => {
                    match link_type {
                        LinkTypes::FixtureUpdates => {
                            validate_create_link_fixture_updates(
                                action,
                                base_address,
                                target_address,
                                tag,
                            )
                        }
                        LinkTypes::AllFixtures => {
                            validate_create_link_all_fixtures(
                                action,
                                base_address,
                                target_address,
                                tag,
                            )
                        }
                    }
                }
                OpRecord::DeleteLink { original_action_hash, base_address, action } => {
                    let record = must_get_valid_record(original_action_hash)?;
                    let create_link = match record.action() {
                        Action::CreateLink(create_link) => create_link.clone(),
                        _ => {
                            return Ok(
                                ValidateCallbackResult::Invalid(
                                    "The action that a DeleteLink deletes must be a CreateLink"
                                        .to_string(),
                                ),
                            );
                        }
                    };
                    let link_type = match LinkTypes::from_type(
                        create_link.zome_index.clone(),
                        create_link.link_type.clone(),
                    )? {
                        Some(lt) => lt,
                        None => return Ok(ValidateCallbackResult::Valid),
                    };
                    match link_type {
                        LinkTypes::FixtureUpdates => {
                            validate_delete_link_fixture_updates(
                                action,
                                create_link.clone(),
                                base_address,
                                create_link.target_address,
                                create_link.tag,
                            )
                        }
                        LinkTypes::AllFixtures => {
                            validate_delete_link_all_fixtures(
                                action,
                                create_link.clone(),
                                base_address,
                                create_link.target_address,
                                create_link.tag,
                            )
                        }
                    }
                }
                OpRecord::CreatePrivateEntry { .. } => Ok(ValidateCallbackResult::Valid),
                OpRecord::UpdatePrivateEntry { .. } => Ok(ValidateCallbackResult::Valid),
                OpRecord::CreateCapClaim { .. } => Ok(ValidateCallbackResult::Valid),
                OpRecord::CreateCapGrant { .. } => Ok(ValidateCallbackResult::Valid),
                OpRecord::UpdateCapClaim { .. } => Ok(ValidateCallbackResult::Valid),
                OpRecord::UpdateCapGrant { .. } => Ok(ValidateCallbackResult::Valid),
                OpRecord::Dna { .. } => Ok(ValidateCallbackResult::Valid),
                OpRecord::OpenChain { .. } => Ok(ValidateCallbackResult::Valid),
                OpRecord::CloseChain { .. } => Ok(ValidateCallbackResult::Valid),
                OpRecord::InitZomesComplete { .. } => Ok(ValidateCallbackResult::Valid),
                _ => Ok(ValidateCallbackResult::Valid),
            }
        }
        FlatOp::RegisterUpdate(update_entry) => {
            match update_entry {
                OpUpdate::Entry { app_entry, action } => {
                    match app_entry {
                        EntryTypes::Fixture(fixture) => {
                            validate_update_fixture(action, fixture)
                        }
                    }
                }
                _ => Ok(ValidateCallbackResult::Valid),
            }
        }
        FlatOp::RegisterDelete(OpDelete { .. }) => Ok(ValidateCallbackResult::Valid),
        FlatOp::RegisterCreateLink {
            link_type,
            base_address,
            target_address,
            tag,
            action,
        } => {
            match link_type {
                LinkTypes::FixtureUpdates => {
                    validate_create_link_fixture_updates(
                        action,
                        base_address,
                        target_address,
                        tag,
                    )
                }
                LinkTypes::AllFixtures => {
                    validate_create_link_all_fixtures(
                        action,
                        base_address,
                        target_address,
                        tag,
                    )
                }
            }
        }
        FlatOp::RegisterDeleteLink {
            link_type,
            base_address,
            target_address,
            tag,
            original_action,
            action,
        } => {
            match link_type {
                LinkTypes::FixtureUpdates => {
                    validate_delete_link_fixture_updates(
                        action,
                        original_action,
                        base_address,
                        target_address,
                        tag,
                    )
                }
                LinkTypes::AllFixtures => {
                    validate_delete_link_all_fixtures(
                        action,
                        original_action,
                        base_address,
                        target_address,
                        tag,
                    )
                }
            }
        }
        FlatOp::RegisterAgentActivity(agent_activity) => {
            match agent_activity {
                OpActivity::CreateAgent { agent, action } => {
                    let previous_action = must_get_action(action.prev_action)?;
                    match previous_action.action() {
                        Action::AgentValidationPkg(
                            AgentValidationPkg { membrane_proof, .. },
                        ) => validate_agent_joining(agent, membrane_proof),
                        _ => {
                            Ok(
                                ValidateCallbackResult::Invalid(
                                    "The previous action for a `CreateAgent` action must be an `AgentValidationPkg`"
                                        .to_string(),
                                ),
                            )
                        }
                    }
                }
                _ => Ok(ValidateCallbackResult::Valid),
            }
        }
    }
}
