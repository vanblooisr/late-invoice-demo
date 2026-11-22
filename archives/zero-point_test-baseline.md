# Zero point: the test baseline before any stage is built

Every requirement of the read side and the write side is written as a test against the
skeleton's signatures. This is the run before any body is written; it is kept so the build
has a fixed target and so a later run can be compared with it.

Interpreter: Python 3.14.6 · pytest 9.2.0 · command: `python -m pytest core/tests -q`
Tree: the commit that adds this file; the run was taken on that tree, with every stage body
still a stub. The per-test table below is the run's outcome list; the raw console output
is the same list in pytest's own format.

## Totals by outcome

| Outcome | Count |
|---|---|
| collected | 234 |
| collection errors | 0 |
| failed (the test body ran and an assertion or a stub stopped it) | 134 |
| errored (a fixture raised before the body ran) | 70 |
| passed | 30 |

## Red tests by reason

The failed and errored rows above, by what stopped them.

| Reason | Count |
|---|---|
| a body raises StageNotBuilt | 203 |
| another stated reason | 1 |

Errored means the `conn` fixture itself raised StageNotBuilt in `db.connect`, so the test
body never ran; its assertions have not been seen to fail yet and will be, once `connect`
has a body and the test reaches its own stub. Both kinds are red for the same reason: the
function under test has no body.

## Per file

| File | Outcomes |
|---|---|
| test_approve | ERROR:StageNotBuilt 11, FAILURE:StageNotBuilt 20, PASS 1 |
| test_cli | PASS 14 |
| test_config | FAILURE:StageNotBuilt 16, PASS 1 |
| test_db | ERROR:StageNotBuilt 34, PASS 6 |
| test_demo | FAILURE:StageNotBuilt 4 |
| test_fetch | ERROR:StageNotBuilt 5, FAILURE:StageNotBuilt 1 |
| test_link | ERROR:StageNotBuilt 8 |
| test_log | FAILURE:StageNotBuilt 18, PASS 1 |
| test_mollie_client | FAILURE:StageNotBuilt 12, PASS 2 |
| test_money | FAILURE:StageNotBuilt 32, PASS 2 |
| test_port_contract | FAILURE:StageNotBuilt 18, PASS 2 |
| test_retry | FAILURE:StageNotBuilt 12, FAILURE:other 1, PASS 1 |
| test_writeback | ERROR:StageNotBuilt 12 |

## Green at the zero point, and why

These tests pin contracts the skeleton already declares (constants, reprs, the command line).
They are kept because the skeleton's contract is part of the baseline; a later change that
breaks one is a regression, not progress. The command-line tests use stand-in stage bodies
that raise the not-implemented error, so they keep passing when the real bodies land.

- `test_approve::test_callback_limit_and_choice_set`: constants declared by the skeleton (CALLBACK_MAX_BYTES, CHOICES, CHOICE_TO_STATUS)
- `test_cli::test_no_arguments_prints_help_and_returns_usage`: the command line was built with the skeleton: parser, exit codes, help and the not-implemented message shape are real (the stage bodies are stand-ins in these tests)
- `test_cli::test_version`: the command line was built with the skeleton: parser, exit codes, help and the not-implemented message shape are real (the stage bodies are stand-ins in these tests)
- `test_cli::test_unimplemented_stage_reports_message_and_exit_code[fetch]`: the command line was built with the skeleton: parser, exit codes, help and the not-implemented message shape are real (the stage bodies are stand-ins in these tests)
- `test_cli::test_unimplemented_stage_reports_message_and_exit_code[approve]`: the command line was built with the skeleton: parser, exit codes, help and the not-implemented message shape are real (the stage bodies are stand-ins in these tests)
- `test_cli::test_unimplemented_stage_reports_message_and_exit_code[link]`: the command line was built with the skeleton: parser, exit codes, help and the not-implemented message shape are real (the stage bodies are stand-ins in these tests)
- `test_cli::test_unimplemented_stage_reports_message_and_exit_code[check]`: the command line was built with the skeleton: parser, exit codes, help and the not-implemented message shape are real (the stage bodies are stand-ins in these tests)
- `test_cli::test_unimplemented_stage_reports_message_and_exit_code[demo]`: the command line was built with the skeleton: parser, exit codes, help and the not-implemented message shape are real (the stage bodies are stand-ins in these tests)
- `test_cli::test_module_entry_has_same_message_body_as_cli`: the command line was built with the skeleton: parser, exit codes, help and the not-implemented message shape are real (the stage bodies are stand-ins in these tests)
- `test_cli::test_unknown_subcommand_is_usage_error`: the command line was built with the skeleton: parser, exit codes, help and the not-implemented message shape are real (the stage bodies are stand-ins in these tests)
- `test_cli::test_help_lists_adapter_flag[fetch]`: the command line was built with the skeleton: parser, exit codes, help and the not-implemented message shape are real (the stage bodies are stand-ins in these tests)
- `test_cli::test_help_lists_adapter_flag[link]`: the command line was built with the skeleton: parser, exit codes, help and the not-implemented message shape are real (the stage bodies are stand-ins in these tests)
- `test_cli::test_help_lists_adapter_flag[check]`: the command line was built with the skeleton: parser, exit codes, help and the not-implemented message shape are real (the stage bodies are stand-ins in these tests)
- `test_cli::test_help_lists_adapter_flag[demo]`: the command line was built with the skeleton: parser, exit codes, help and the not-implemented message shape are real (the stage bodies are stand-ins in these tests)
- `test_cli::test_approve_help_has_no_adapter_flag`: the command line was built with the skeleton: parser, exit codes, help and the not-implemented message shape are real (the stage bodies are stand-ins in these tests)
- `test_config::test_settings_repr_and_str_hide_values`: Settings.__repr__ is implemented in the skeleton (name-only repr)
- `test_db::test_statuses_are_exactly_six`: constants declared by the skeleton (STATUSES, TERMINAL_STATUSES, TRANSITIONS)
- `test_db::test_statuses_equal_the_named_constants_in_order`: constants declared by the skeleton (STATUSES, TERMINAL_STATUSES, TRANSITIONS)
- `test_db::test_transitions_have_six_keys_one_per_status`: constants declared by the skeleton (STATUSES, TERMINAL_STATUSES, TRANSITIONS)
- `test_db::test_transitions_are_forward_only`: constants declared by the skeleton (STATUSES, TERMINAL_STATUSES, TRANSITIONS)
- `test_db::test_terminal_statuses_map_to_empty_frozensets`: constants declared by the skeleton (STATUSES, TERMINAL_STATUSES, TRANSITIONS)
- `test_db::test_allowed_edges_match_the_transition_table`: constants declared by the skeleton (STATUSES, TERMINAL_STATUSES, TRANSITIONS)
- `test_log::test_redacted_marker`: constant declared by the skeleton (REDACTED)
- `test_mollie_client::test_repr_hides_key`: MollieClient.__repr__ is implemented in the skeleton
- `test_mollie_client::test_live_key_is_refused`: the constructor's test_-key check is implemented in the skeleton
- `test_money::test_money_error_is_value_error`: MoneyError is declared as a ValueError subclass in the skeleton
- `test_money::test_amount_pattern_constant`: constant declared by the skeleton (AMOUNT_PATTERN)
- `test_port_contract::test_is_a_bookkeeping_port[fake]`: the Protocol check is structural; both adapters declare the four verbs
- `test_port_contract::test_is_a_bookkeeping_port[moneybird]`: the Protocol check is structural; both adapters declare the four verbs
- `test_retry::test_retry_attempts_constant`: constant declared by the skeleton (RETRY_ATTEMPTS)

## Red for a reason other than StageNotBuilt

- `test_retry::test_other_errors_are_not_retried[stage-not-built]`: `assert 0 == 1`

## Every test

| File | Test | Outcome | Reason |
|---|---|---|---|
| test_approve | test_callback_limit_and_choice_set | PASS |  |
| test_approve | test_parse_valid | FAILURE | StageNotBuilt |
| test_approve | test_parse_accepts_exactly_64_bytes | FAILURE | StageNotBuilt |
| test_approve | test_parse_rejects_over_64_bytes | FAILURE | StageNotBuilt |
| test_approve | test_parse_counts_bytes_not_characters | FAILURE | StageNotBuilt |
| test_approve | test_parse_rejects_bad_content[12:maybe] | FAILURE | StageNotBuilt |
| test_approve | test_parse_rejects_bad_content[x:approve] | FAILURE | StageNotBuilt |
| test_approve | test_parse_rejects_bad_content[0:approve] | FAILURE | StageNotBuilt |
| test_approve | test_parse_rejects_bad_content[-1:approve] | FAILURE | StageNotBuilt |
| test_approve | test_parse_rejects_bad_content[+12:approve] | FAILURE | StageNotBuilt |
| test_approve | test_parse_rejects_bad_content[ 12:approve] | FAILURE | StageNotBuilt |
| test_approve | test_parse_rejects_bad_content[12 :approve] | FAILURE | StageNotBuilt |
| test_approve | test_parse_rejects_bad_content[1_2:approve] | FAILURE | StageNotBuilt |
| test_approve | test_parse_rejects_bad_content[\uff11\uff12:approve] | FAILURE | StageNotBuilt |
| test_approve | test_parse_rejects_bad_content[012:approve] | FAILURE | StageNotBuilt |
| test_approve | test_parse_rejects_bad_content[12:approve:x] | FAILURE | StageNotBuilt |
| test_approve | test_parse_rejects_bad_content[12:APPROVE] | FAILURE | StageNotBuilt |
| test_approve | test_parse_rejects_bad_content[12] | FAILURE | StageNotBuilt |
| test_approve | test_parse_rejects_bad_content[:approve] | FAILURE | StageNotBuilt |
| test_approve | test_parse_rejects_bad_content[] | FAILURE | StageNotBuilt |
| test_approve | test_parse_rejects_bad_content[12:approve ] | FAILURE | StageNotBuilt |
| test_approve | test_foreign_chat_is_ignored_and_logged | ERROR | StageNotBuilt |
| test_approve | test_empty_allowed_chat_refuses_every_tap[111] | ERROR | StageNotBuilt |
| test_approve | test_empty_allowed_chat_refuses_every_tap[999] | ERROR | StageNotBuilt |
| test_approve | test_empty_allowed_chat_refuses_every_tap[] | ERROR | StageNotBuilt |
| test_approve | test_malformed_data_is_false_and_logged | ERROR | StageNotBuilt |
| test_approve | test_unknown_action_id_is_false_and_logged | ERROR | StageNotBuilt |
| test_approve | test_row_not_pending_is_noop_and_logged | ERROR | StageNotBuilt |
| test_approve | test_approve_moves_row_to_approved | ERROR | StageNotBuilt |
| test_approve | test_reject_moves_row_to_rejected | ERROR | StageNotBuilt |
| test_approve | test_send_proposals_sends_once_per_invoice | ERROR | StageNotBuilt |
| test_approve | test_failed_send_stops_the_run_and_is_retried | ERROR | StageNotBuilt |
| test_cli | test_no_arguments_prints_help_and_returns_usage | PASS |  |
| test_cli | test_version | PASS |  |
| test_cli | test_unimplemented_stage_reports_message_and_exit_code[fetch] | PASS |  |
| test_cli | test_unimplemented_stage_reports_message_and_exit_code[approve] | PASS |  |
| test_cli | test_unimplemented_stage_reports_message_and_exit_code[link] | PASS |  |
| test_cli | test_unimplemented_stage_reports_message_and_exit_code[check] | PASS |  |
| test_cli | test_unimplemented_stage_reports_message_and_exit_code[demo] | PASS |  |
| test_cli | test_module_entry_has_same_message_body_as_cli | PASS |  |
| test_cli | test_unknown_subcommand_is_usage_error | PASS |  |
| test_cli | test_help_lists_adapter_flag[fetch] | PASS |  |
| test_cli | test_help_lists_adapter_flag[link] | PASS |  |
| test_cli | test_help_lists_adapter_flag[check] | PASS |  |
| test_cli | test_help_lists_adapter_flag[demo] | PASS |  |
| test_cli | test_approve_help_has_no_adapter_flag | PASS |  |
| test_config | test_load_reads_dotenv_file | FAILURE | StageNotBuilt |
| test_config | test_process_env_overrides_file | FAILURE | StageNotBuilt |
| test_config | test_missing_variables_are_none | FAILURE | StageNotBuilt |
| test_config | test_non_test_mollie_key_refused_from_file[live_dummy_key_for_tests] | FAILURE | StageNotBuilt |
| test_config | test_non_test_mollie_key_refused_from_file[access_dummy_token_for_tests] | FAILURE | StageNotBuilt |
| test_config | test_non_test_mollie_key_refused_from_file[LIVE_dummy] | FAILURE | StageNotBuilt |
| test_config | test_non_test_mollie_key_refused_from_file[ test_dummy_key_for_tests] | FAILURE | StageNotBuilt |
| test_config | test_non_test_mollie_key_refused_from_file[dummy_key_without_prefix] | FAILURE | StageNotBuilt |
| test_config | test_non_test_mollie_key_refused_from_process_env | FAILURE | StageNotBuilt |
| test_config | test_test_mollie_key_accepted | FAILURE | StageNotBuilt |
| test_config | test_require_names_missing_variable | FAILURE | StageNotBuilt |
| test_config | test_require_passes_when_set | FAILURE | StageNotBuilt |
| test_config | test_resolve_db_path_flag_wins | FAILURE | StageNotBuilt |
| test_config | test_resolve_db_path_settings_over_default | FAILURE | StageNotBuilt |
| test_config | test_resolve_db_path_default_and_absolute | FAILURE | StageNotBuilt |
| test_config | test_resolve_db_path_always_absolute | FAILURE | StageNotBuilt |
| test_config | test_settings_repr_and_str_hide_values | PASS |  |
| test_db | test_insert_pending_returns_row | ERROR | StageNotBuilt |
| test_db | test_insert_pending_twice_is_idempotent | ERROR | StageNotBuilt |
| test_db | test_allowed_edge[pending-approved] | ERROR | StageNotBuilt |
| test_db | test_allowed_edge[pending-rejected] | ERROR | StageNotBuilt |
| test_db | test_allowed_edge[approved-link_created] | ERROR | StageNotBuilt |
| test_db | test_allowed_edge[link_created-paid] | ERROR | StageNotBuilt |
| test_db | test_allowed_edge[link_created-paid_elsewhere] | ERROR | StageNotBuilt |
| test_db | test_forbidden_edge_raises_and_leaves_row[approved-pending] | ERROR | StageNotBuilt |
| test_db | test_forbidden_edge_raises_and_leaves_row[link_created-approved] | ERROR | StageNotBuilt |
| test_db | test_forbidden_edge_raises_and_leaves_row[paid-link_created] | ERROR | StageNotBuilt |
| test_db | test_forbidden_edge_raises_and_leaves_row[pending-link_created] | ERROR | StageNotBuilt |
| test_db | test_forbidden_edge_raises_and_leaves_row[pending-paid] | ERROR | StageNotBuilt |
| test_db | test_forbidden_edge_raises_and_leaves_row[approved-paid] | ERROR | StageNotBuilt |
| test_db | test_forbidden_edge_raises_and_leaves_row[rejected-approved] | ERROR | StageNotBuilt |
| test_db | test_forbidden_edge_raises_and_leaves_row[paid-pending] | ERROR | StageNotBuilt |
| test_db | test_forbidden_edge_raises_and_leaves_row[paid-approved] | ERROR | StageNotBuilt |
| test_db | test_forbidden_edge_raises_and_leaves_row[paid-paid_elsewhere] | ERROR | StageNotBuilt |
| test_db | test_forbidden_edge_raises_and_leaves_row[paid_elsewhere-paid] | ERROR | StageNotBuilt |
| test_db | test_forbidden_edge_raises_and_leaves_row[paid_elsewhere-pending] | ERROR | StageNotBuilt |
| test_db | test_unknown_status_name_raises_and_leaves_row[pending-bogus] | ERROR | StageNotBuilt |
| test_db | test_unknown_status_name_raises_and_leaves_row[bogus-approved] | ERROR | StageNotBuilt |
| test_db | test_lost_race_returns_false_and_leaves_row[pending-approved] | ERROR | StageNotBuilt |
| test_db | test_lost_race_returns_false_and_leaves_row[pending-rejected] | ERROR | StageNotBuilt |
| test_db | test_lost_race_returns_false_and_leaves_row[approved-link_created] | ERROR | StageNotBuilt |
| test_db | test_lost_race_returns_false_and_leaves_row[link_created-paid] | ERROR | StageNotBuilt |
| test_db | test_lost_race_returns_false_and_leaves_row[link_created-paid_elsewhere] | ERROR | StageNotBuilt |
| test_db | test_list_rows_filters_and_orders | ERROR | StageNotBuilt |
| test_db | test_row_fields_are_typed | ERROR | StageNotBuilt |
| test_db | test_get_row_returns_row_by_id | ERROR | StageNotBuilt |
| test_db | test_get_row_unknown_id_is_none | ERROR | StageNotBuilt |
| test_db | test_mark_messaged_sets_timestamp_once | ERROR | StageNotBuilt |
| test_db | test_set_link_on_approved_row_moves_to_link_created | ERROR | StageNotBuilt |
| test_db | test_set_link_on_pending_row_is_refused_and_leaves_row | ERROR | StageNotBuilt |
| test_db | test_set_link_twice_second_call_is_false | ERROR | StageNotBuilt |
| test_db | test_statuses_are_exactly_six | PASS |  |
| test_db | test_statuses_equal_the_named_constants_in_order | PASS |  |
| test_db | test_transitions_have_six_keys_one_per_status | PASS |  |
| test_db | test_transitions_are_forward_only | PASS |  |
| test_db | test_terminal_statuses_map_to_empty_frozensets | PASS |  |
| test_db | test_allowed_edges_match_the_transition_table | PASS |  |
| test_demo | test_run_returns_zero | FAILURE | StageNotBuilt |
| test_demo | test_three_clean_runs_keep_row_count_stable | FAILURE | StageNotBuilt |
| test_demo | test_log_names_every_stage | FAILURE | StageNotBuilt |
| test_demo | test_no_keys_on_screen_or_in_log | FAILURE | StageNotBuilt |
| test_fetch | test_fetch_records_one_pending_row_per_late_invoice | ERROR | StageNotBuilt |
| test_fetch | test_fetch_twice_leaves_rows_unchanged | ERROR | StageNotBuilt |
| test_fetch | test_mixed_batch_with_unknown_state_writes_nothing | ERROR | StageNotBuilt |
| test_fetch | test_paid_state_batch_is_refused | ERROR | StageNotBuilt |
| test_fetch | test_non_eur_batch_is_refused | ERROR | StageNotBuilt |
| test_fetch | test_run_end_to_end_twice | FAILURE | StageNotBuilt |
| test_link | test_creates_one_link_per_approvedrow_for | ERROR | StageNotBuilt |
| test_link | test_already_paid_invoice_gets_no_link | ERROR | StageNotBuilt |
| test_link | test_second_run_creates_no_second_link | ERROR | StageNotBuilt |
| test_link | test_three_failed_connections_cancel_and_report | ERROR | StageNotBuilt |
| test_link | test_timeout_after_post_creates_no_second_link | ERROR | StageNotBuilt |
| test_link | test_idempotency_key_is_invoice_id_and_row_id | ERROR | StageNotBuilt |
| test_link | test_post_body_carries_an_expiry_of_link_lifetime | ERROR | StageNotBuilt |
| test_link | test_send_is_called_once_per_created_link | ERROR | StageNotBuilt |
| test_log | test_redacted_marker | PASS |  |
| test_log | test_exact_secret_replaced_everywhere | FAILURE | StageNotBuilt |
| test_log | test_bearer_token_removed[Bearer] | FAILURE | StageNotBuilt |
| test_log | test_bearer_token_removed[bearer] | FAILURE | StageNotBuilt |
| test_log | test_query_value_redacted_key_kept[api_key] | FAILURE | StageNotBuilt |
| test_log | test_query_value_redacted_key_kept[token] | FAILURE | StageNotBuilt |
| test_log | test_query_value_redacted_key_kept[access_token] | FAILURE | StageNotBuilt |
| test_log | test_query_value_redacted_key_kept[key] | FAILURE | StageNotBuilt |
| test_log | test_query_value_redacted_key_kept[API_KEY] | FAILURE | StageNotBuilt |
| test_log | test_telegram_path_segment_redacted | FAILURE | StageNotBuilt |
| test_log | test_run_at_threshold_redacted | FAILURE | StageNotBuilt |
| test_log | test_run_below_threshold_and_words_survive | FAILURE | StageNotBuilt |
| test_log | test_plain_text_unchanged | FAILURE | StageNotBuilt |
| test_log | test_install_redaction_covers_third_party_and_root | FAILURE | StageNotBuilt |
| test_log | test_install_redaction_covers_percent_style_argument | FAILURE | StageNotBuilt |
| test_log | test_install_redaction_covers_exc_info | FAILURE | StageNotBuilt |
| test_log | test_install_redaction_covers_telegram_logger | FAILURE | StageNotBuilt |
| test_log | test_install_redaction_covers_handler_attached_afterwards | FAILURE | StageNotBuilt |
| test_log | test_install_redaction_quiets_http_loggers | FAILURE | StageNotBuilt |
| test_mollie_client | test_create_returns_payment_link | FAILURE | StageNotBuilt |
| test_mollie_client | test_create_request_shape | FAILURE | StageNotBuilt |
| test_mollie_client | test_default_expiry_is_now_plus_link_lifetime | FAILURE | StageNotBuilt |
| test_mollie_client | test_every_request_carries_bearer_key | FAILURE | StageNotBuilt |
| test_mollie_client | test_get_paid_link_reads_paid_time_and_amount_from_payments | FAILURE | StageNotBuilt |
| test_mollie_client | test_non_paid_payment_is_excluded_from_the_paid_amount | FAILURE | StageNotBuilt |
| test_mollie_client | test_three_decimal_paid_amount_fails_closed | FAILURE | StageNotBuilt |
| test_mollie_client | test_get_unpaid_link_has_no_paid_values | FAILURE | StageNotBuilt |
| test_mollie_client | test_three_decimal_amount_fails_closed | FAILURE | StageNotBuilt |
| test_mollie_client | test_unknown_link_is_an_error | FAILURE | StageNotBuilt |
| test_mollie_client | test_deactivate_sends_archive_patch | FAILURE | StageNotBuilt |
| test_mollie_client | test_repr_hides_key | PASS |  |
| test_mollie_client | test_key_appears_in_no_url_body_or_error | FAILURE | StageNotBuilt |
| test_mollie_client | test_live_key_is_refused | PASS |  |
| test_money | test_money_error_is_value_error | PASS |  |
| test_money | test_cents_to_str_formats_two_decimal_places | FAILURE | StageNotBuilt |
| test_money | test_cents_to_str_small_values | FAILURE | StageNotBuilt |
| test_money | test_str_to_cents_parses_two_decimal_string | FAILURE | StageNotBuilt |
| test_money | test_round_trip_from_cents[0] | FAILURE | StageNotBuilt |
| test_money | test_round_trip_from_cents[1] | FAILURE | StageNotBuilt |
| test_money | test_round_trip_from_cents[5] | FAILURE | StageNotBuilt |
| test_money | test_round_trip_from_cents[99] | FAILURE | StageNotBuilt |
| test_money | test_round_trip_from_cents[100] | FAILURE | StageNotBuilt |
| test_money | test_round_trip_from_cents[12100] | FAILURE | StageNotBuilt |
| test_money | test_round_trip_from_cents[99999999] | FAILURE | StageNotBuilt |
| test_money | test_round_trip_from_string[0.00] | FAILURE | StageNotBuilt |
| test_money | test_round_trip_from_string[0.05] | FAILURE | StageNotBuilt |
| test_money | test_round_trip_from_string[1.00] | FAILURE | StageNotBuilt |
| test_money | test_round_trip_from_string[121.00] | FAILURE | StageNotBuilt |
| test_money | test_round_trip_from_string[999999.99] | FAILURE | StageNotBuilt |
| test_money | test_cents_to_str_rejects[float] | FAILURE | StageNotBuilt |
| test_money | test_cents_to_str_rejects[bool-true-is-int] | FAILURE | StageNotBuilt |
| test_money | test_cents_to_str_rejects[bool-false-is-int] | FAILURE | StageNotBuilt |
| test_money | test_cents_to_str_rejects[negative] | FAILURE | StageNotBuilt |
| test_money | test_str_to_cents_rejects[121,00] | FAILURE | StageNotBuilt |
| test_money | test_str_to_cents_rejects[1.000,00] | FAILURE | StageNotBuilt |
| test_money | test_str_to_cents_rejects[121.0] | FAILURE | StageNotBuilt |
| test_money | test_str_to_cents_rejects[121.000] | FAILURE | StageNotBuilt |
| test_money | test_str_to_cents_rejects[ 121.00] | FAILURE | StageNotBuilt |
| test_money | test_str_to_cents_rejects[121.00\n] | FAILURE | StageNotBuilt |
| test_money | test_str_to_cents_rejects[\u20ac121.00] | FAILURE | StageNotBuilt |
| test_money | test_str_to_cents_rejects[-1.00] | FAILURE | StageNotBuilt |
| test_money | test_str_to_cents_rejects[+1.00] | FAILURE | StageNotBuilt |
| test_money | test_str_to_cents_rejects[abc] | FAILURE | StageNotBuilt |
| test_money | test_str_to_cents_rejects[] | FAILURE | StageNotBuilt |
| test_money | test_str_to_cents_rejects[\u0661\u0662\u0661.00] | FAILURE | StageNotBuilt |
| test_money | test_str_to_cents_rejects[\uff11\uff12\uff11.00] | FAILURE | StageNotBuilt |
| test_money | test_amount_pattern_constant | PASS |  |
| test_port_contract | test_is_a_bookkeeping_port[fake] | PASS |  |
| test_port_contract | test_is_a_bookkeeping_port[moneybird] | PASS |  |
| test_port_contract | test_list_late_invoices_shape[fake] | FAILURE | StageNotBuilt |
| test_port_contract | test_list_late_invoices_shape[moneybird] | FAILURE | StageNotBuilt |
| test_port_contract | test_list_late_invoices_values[fake] | FAILURE | StageNotBuilt |
| test_port_contract | test_list_late_invoices_values[moneybird] | FAILURE | StageNotBuilt |
| test_port_contract | test_get_invoice_returns_each_late_invoice[fake] | FAILURE | StageNotBuilt |
| test_port_contract | test_get_invoice_returns_each_late_invoice[moneybird] | FAILURE | StageNotBuilt |
| test_port_contract | test_get_invoice_unknown_id_raises[fake] | FAILURE | StageNotBuilt |
| test_port_contract | test_get_invoice_unknown_id_raises[moneybird] | FAILURE | StageNotBuilt |
| test_port_contract | test_register_payment_marks_invoice_paid[fake] | FAILURE | StageNotBuilt |
| test_port_contract | test_register_payment_marks_invoice_paid[moneybird] | FAILURE | StageNotBuilt |
| test_port_contract | test_register_payment_on_paid_invoice_raises[fake] | FAILURE | StageNotBuilt |
| test_port_contract | test_register_payment_on_paid_invoice_raises[moneybird] | FAILURE | StageNotBuilt |
| test_port_contract | test_get_contact_support[fake_adapter-False] | FAILURE | StageNotBuilt |
| test_port_contract | test_get_contact_support[moneybird_and_server-True] | FAILURE | StageNotBuilt |
| test_port_contract | test_moneybird_sends_bearer_token_and_late_filter | FAILURE | StageNotBuilt |
| test_port_contract | test_moneybird_token_not_in_repr | FAILURE | StageNotBuilt |
| test_port_contract | test_moneybird_wire_requests | FAILURE | StageNotBuilt |
| test_port_contract | test_moneybird_token_never_leaks | FAILURE | StageNotBuilt |
| test_retry | test_three_failures_then_reraise_last | FAILURE | StageNotBuilt |
| test_retry | test_recovers_on_third_attempt | FAILURE | StageNotBuilt |
| test_retry | test_connection_errors_are_retried[exc0] | FAILURE | StageNotBuilt |
| test_retry | test_connection_errors_are_retried[exc1] | FAILURE | StageNotBuilt |
| test_retry | test_connection_errors_are_retried[exc2] | FAILURE | StageNotBuilt |
| test_retry | test_other_errors_are_not_retried[value-error] | FAILURE | StageNotBuilt |
| test_retry | test_other_errors_are_not_retried[stage-not-built] | FAILURE | assert 0 == 1 |
| test_retry | test_other_errors_are_not_retried[unsupported-verb] | FAILURE | StageNotBuilt |
| test_retry | test_other_errors_are_not_retried[money-error] | FAILURE | StageNotBuilt |
| test_retry | test_other_errors_are_not_retried[permission-error] | FAILURE | StageNotBuilt |
| test_retry | test_other_errors_are_not_retried[http-429] | FAILURE | StageNotBuilt |
| test_retry | test_attempts_one_means_no_retry | FAILURE | StageNotBuilt |
| test_retry | test_sleep_hook_runs_between_attempts_never_after_the_last | FAILURE | StageNotBuilt |
| test_retry | test_retry_attempts_constant | PASS |  |
| test_writeback | test_paid_link_is_booked | ERROR | StageNotBuilt |
| test_writeback | test_running_twice_books_once | ERROR | StageNotBuilt |
| test_writeback | test_booking_call_carries_id_amount_and_the_links_paid_time | ERROR | StageNotBuilt |
| test_writeback | test_rows_outside_link_created_are_never_booked | ERROR | StageNotBuilt |
| test_writeback | test_unpaid_link_is_not_booked | ERROR | StageNotBuilt |
| test_writeback | test_invoice_paid_elsewhere_with_paid_link_is_not_booked_again | ERROR | StageNotBuilt |
| test_writeback | test_invoice_paid_elsewhere_with_unpaid_link_archives_the_link | ERROR | StageNotBuilt |
| test_writeback | test_amount_mismatch_is_not_booked_and_is_reported[100.00-paid_forms0] | ERROR | StageNotBuilt |
| test_writeback | test_amount_mismatch_is_not_booked_and_is_reported[120.99-paid_forms1] | ERROR | StageNotBuilt |
| test_writeback | test_amount_mismatch_is_not_booked_and_is_reported[121.01-paid_forms2] | ERROR | StageNotBuilt |
| test_writeback | test_successful_booking_is_sent | ERROR | StageNotBuilt |
| test_writeback | test_paid_elsewhere_with_paid_link_is_sent_as_refund | ERROR | StageNotBuilt |
