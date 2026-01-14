# Old Code Archive

This directory contains archived versions of refactored code.

## start.py

The original `src/bot/handlers/start.py` file (~1.2k lines) was refactored into a modular structure:

- `src/bot/handlers/start/router.py` - Router registration and handler bindings
- `src/bot/handlers/start/commands.py` - Command handlers and callback handlers
- `src/bot/handlers/start/services/onboarding_service.py` - User onboarding business logic
- `src/bot/handlers/start/services/pair_service.py` - Pair management business logic
- `src/bot/handlers/start/ui/builders.py` - UI elements (keyboards, text formatting)

## telegram.py

The original `src/services/telegram.py` file (~539 lines) was refactored into a modular structure:

- `src/services/telegram/bot_provider.py` - Bot instance provider with dependency injection support (replaces global singleton)
- `src/services/telegram/messenger.py` - Message sending/editing/deleting with retry logic
- `src/services/telegram/message_store.py` - Interface and implementation for saving message IDs to database
- `src/services/telegram/retry.py` - Common retry policy mechanism for Telegram API calls
- `src/services/telegram/__init__.py` - Public API with backward compatibility functions

**Benefits:**
- Eliminated global singleton pattern (replaced with DI)
- Removed code duplication (retry logic extracted)
- Better separation of concerns (message storage abstracted)
- Improved testability (interfaces and dependency injection)

## payment.py

The original `src/services/payment.py` file (~443 lines) was refactored into a modular structure:

- `src/services/payment/circuit_breaker.py` - Universal circuit breaker for external services
- `src/services/payment/interfaces.py` - Abstract interfaces for payment providers (PaymentProvider)
- `src/services/payment/robokassa_service.py` - Robokassa payment provider implementation
- `src/services/payment/webhook_handler.py` - Handler for Robokassa ResultURL webhooks
- `src/services/payment/__init__.py` - Public API with backward compatibility wrapper

**Benefits:**
- Separation of concerns (circuit breaker, payment creation, webhook handling)
- Easy to add new payment providers (implement PaymentProvider interface)
- Universal circuit breaker can be reused for other services
- Improved testability (interfaces and dependency injection)

## run.py, bot/main.py, worker/main.py

The original entry point files were refactored to extract common bootstrap logic:

- `src/core/bootstrap.py` - Application bootstrap: logging configuration, env loading, DI container preparation
- `src/bot/app.py` - Bot application factory: `create_bot_app(container)` creates Bot/Dispatcher with middleware and handlers
- `src/worker/app.py` - Worker application factory: `create_worker(container)` creates arq Worker instance
- `run.py` (updated) - Uses bootstrap and app factories
- `src/bot/main.py` (updated) - Uses bootstrap and bot app factory
- `src/worker/main.py` (updated) - Uses bootstrap and worker app factory

**Benefits:**
- Single point of configuration (bootstrap)
- Less code duplication between CLI scripts
- Dependency injection container for shared resources
- Easier testing (app factories can be called with test containers)
- Clear separation of concerns (bootstrap vs app creation)
