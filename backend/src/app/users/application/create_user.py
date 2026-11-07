"""Register a user — single use-case interactor with explicit boundaries."""

from dataclasses import dataclass

from app.shared.application.unit_of_work import UnitOfWork
from app.shared.domain.id_generator import IdGenerator
from app.users.application.errors import EmailAlreadyRegisteredError
from app.users.domain.user import User
from app.users.domain.user_id import UserId
from app.users.ports.user_repository import UserRepository


@dataclass(frozen=True, slots=True)
class CreateUserRequest:
    """Input DTO for the create-user use case (owned by the inner layer)."""

    email: str
    first_name: str
    last_name: str


@dataclass(frozen=True, slots=True)
class CreateUserResponse:
    """Output DTO for the create-user use case — never expose the domain entity directly."""

    id: UserId
    email: str
    first_name: str
    last_name: str


class CreateUser:
    """Create and persist a user in a single transaction."""

    def __init__(
        self,
        users: UserRepository,
        unit_of_work: UnitOfWork,
        id_generator: IdGenerator,
    ) -> None:
        self._users = users
        self._unit_of_work = unit_of_work
        self._id_generator = id_generator

    def execute(self, request: CreateUserRequest) -> CreateUserResponse:
        with self._unit_of_work:
            if self._users.get_by_email(request.email) is not None:
                raise EmailAlreadyRegisteredError(request.email)

            user = User(
                id=UserId(f"user_{self._id_generator.new_uuid()}"),
                email=request.email,
                first_name=request.first_name,
                last_name=request.last_name,
            )
            self._users.add(user)
            self._unit_of_work.commit()
            return CreateUserResponse(
                id=user.id,
                email=user.email,
                first_name=user.first_name,
                last_name=user.last_name,
            )
