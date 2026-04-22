# RBAC Administration API Documentation

## Overview

Complete Role-Based Access Control (RBAC) management API for the Medical Tourism Platform. All endpoints are located under `/api/v1/admin/rbac` and require **admin authentication**.

- **Base URL**: `/api/v1/admin/rbac`
- **Authentication**: Bearer Token (JWT)
- **Required Role**: Admin or higher
- **All responses** include proper HTTP status codes and error messages

---

## 1. Dashboard Statistics

### GET /stats

Retrieve dashboard statistics for the RBAC management dashboard.

**Authentication**: ✅ Required (Admin+)

**Request**:
```bash
GET /api/v1/admin/rbac/stats
Authorization: Bearer <token>
```

**Response** (200 OK):
```json
{
  "total_roles": 6,
  "assigned_users": 24,
  "admin_users": 3,
  "hotels_with_manager": 15,
  "apartments_with_manager": 8,
  "restaurants_with_manager": 5
}
```

**Response Schema**:
```python
class RBACStatsResponse(BaseSchema):
    total_roles: int
    assigned_users: int
    admin_users: int
    hotels_with_manager: int
    apartments_with_manager: int
    restaurants_with_manager: int
```

---

## 2. Role Management

### GET /roles

List all roles with pagination and user count.

**Authentication**: ✅ Required (Admin+)

**Request**:
```bash
GET /api/v1/admin/rbac/roles?page=1&page_size=50
Authorization: Bearer <token>
```

**Query Parameters**:
| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| page | int | 1 | Page number |
| page_size | int | 50 | Items per page |

**Response** (200 OK):
```json
{
  "items": [
    {
      "id": "uuid-here",
      "name": "hotel_manager",
      "label": "Hotel Manager",
      "description": "Manage hotel properties and bookings",
      "is_system_role": false,
      "user_count": 12,
      "created_at": "2024-01-15T10:00:00Z",
      "created_by": "admin-uuid"
    }
  ],
  "total": 6,
  "page": 1,
  "page_size": 50,
  "total_pages": 1
}
```

**Response Schema**:
```python
class RoleResponse(BaseSchema):
    id: UUID
    name: str
    label: str
    description: Optional[str]
    is_system_role: bool
    user_count: int
    created_at: datetime
    created_by: UUID

class PaginatedResponse(BaseSchema):
    items: List[RoleResponse]
    total: int
    page: int
    page_size: int
    total_pages: int
```

---

### GET /roles/{role_id}

Get detailed information about a specific role including its permissions matrix.

**Authentication**: ✅ Required (Admin+)

**Request**:
```bash
GET /api/v1/admin/rbac/roles/{role_id}
Authorization: Bearer <token>
```

**Path Parameters**:
| Parameter | Type | Description |
|-----------|------|-------------|
| role_id | UUID | Role identifier |

**Response** (200 OK):
```json
{
  "id": "uuid-here",
  "name": "hotel_manager",
  "label": "Hotel Manager",
  "description": "Manage hotel properties and bookings",
  "is_system_role": false,
  "permissions": {
    "hotels": {
      "can_create": false,
      "can_read": true,
      "can_update": true,
      "can_delete": false
    },
    "bookings": {
      "can_create": false,
      "can_read": true,
      "can_update": true,
      "can_delete": false
    }
  },
  "user_count": 12,
  "created_at": "2024-01-15T10:00:00Z",
  "created_by": "admin-uuid"
}
```

**Response Schema**:
```python
class PermissionResponse(BaseSchema):
    can_create: bool
    can_read: bool
    can_update: bool
    can_delete: bool

class RoleDetailResponse(BaseSchema):
    id: UUID
    name: str
    label: str
    description: Optional[str]
    is_system_role: bool
    permissions: Dict[str, PermissionResponse]
    user_count: int
    created_at: datetime
    created_by: UUID
```

**Error Responses**:
- `404 Not Found`: Role does not exist
- `403 Forbidden`: Insufficient permissions

---

### POST /roles

Create a new custom role.

**Authentication**: ✅ Required (Super Admin+)

**Request**:
```bash
POST /api/v1/admin/rbac/roles
Authorization: Bearer <token>
Content-Type: application/json

{
  "name": "content_manager",
  "label": "Content Manager",
  "description": "Manage website content and pages"
}
```

**Request Schema**:
```python
class RoleCreate(BaseSchema):
    name: str  # Unique, lowercase
    label: str  # Display name
    description: Optional[str]
```

**Response** (201 Created):
```json
{
  "id": "new-uuid",
  "name": "content_manager",
  "label": "Content Manager",
  "description": "Manage website content and pages",
  "is_system_role": false,
  "user_count": 0,
  "created_at": "2024-01-16T09:30:00Z",
  "created_by": "admin-uuid"
}
```

**Error Responses**:
- `400 Bad Request`: Name already exists or invalid format
- `403 Forbidden`: Insufficient permissions

---

### PATCH /roles/{role_id}

Update an existing role.

**Authentication**: ✅ Required (Super Admin+)

**Request**:
```bash
PATCH /api/v1/admin/rbac/roles/{role_id}
Authorization: Bearer <token>
Content-Type: application/json

{
  "label": "Hotel Manager (Updated)",
  "description": "Updated description"
}
```

**Request Schema**:
```python
class RoleUpdate(BaseSchema):
    label: Optional[str]
    description: Optional[str]
```

**Response** (200 OK):
```json
{
  "id": "role-uuid",
  "name": "hotel_manager",
  "label": "Hotel Manager (Updated)",
  "description": "Updated description",
  "is_system_role": false,
  "user_count": 12,
  "created_at": "2024-01-15T10:00:00Z",
  "created_by": "admin-uuid"
}
```

**Error Responses**:
- `404 Not Found`: Role not found
- `400 Bad Request`: Cannot modify system roles
- `403 Forbidden`: Insufficient permissions

---

### DELETE /roles/{role_id}

Delete a custom role (soft delete). Cannot delete system roles or roles with assigned users.

**Authentication**: ✅ Required (Super Admin+)

**Request**:
```bash
DELETE /api/v1/admin/rbac/roles/{role_id}
Authorization: Bearer <token>
```

**Response** (204 No Content):
```
(empty body)
```

**Error Responses**:
- `404 Not Found`: Role not found
- `400 Bad Request`: Cannot delete system roles or roles with assigned users
- `403 Forbidden`: Insufficient permissions

---

## 3. Permissions Management

### GET /roles/{role_id}/permissions

Retrieve the permissions matrix for a specific role.

**Authentication**: ✅ Required (Admin+)

**Request**:
```bash
GET /api/v1/admin/rbac/roles/{role_id}/permissions
Authorization: Bearer <token>
```

**Response** (200 OK):
```json
{
  "role_id": "role-uuid",
  "role_name": "hotel_manager",
  "resources": [
    {
      "resource": "hotels",
      "can_create": false,
      "can_read": true,
      "can_update": true,
      "can_delete": false
    },
    {
      "resource": "bookings",
      "can_create": false,
      "can_read": true,
      "can_update": true,
      "can_delete": false
    },
    {
      "resource": "consultations",
      "can_create": false,
      "can_read": true,
      "can_update": false,
      "can_delete": false
    }
  ],
  "scope_own_only": true
}
```

**Response Schema**:
```python
class PermissionMatrixItem(BaseSchema):
    resource: str
    can_create: bool
    can_read: bool
    can_update: bool
    can_delete: bool

class RolePermissionsResponse(BaseSchema):
    role_id: UUID
    role_name: str
    resources: List[PermissionMatrixItem]
    scope_own_only: bool
```

---

### PUT /roles/{role_id}/permissions

Update the permissions matrix for a role.

**Authentication**: ✅ Required (Super Admin+)

**Request**:
```bash
PUT /api/v1/admin/rbac/roles/{role_id}/permissions
Authorization: Bearer <token>
Content-Type: application/json

{
  "permissions": {
    "hotels": {
      "can_create": true,
      "can_read": true,
      "can_update": true,
      "can_delete": false
    },
    "bookings": {
      "can_create": false,
      "can_read": true,
      "can_update": true,
      "can_delete": false
    }
  },
  "scope_own_only": true
}
```

**Request Schema**:
```python
class RolePermissionsUpdate(BaseSchema):
    permissions: Dict[str, Dict[str, bool]]  # {resource: {can_create, can_read, can_update, can_delete}}
    scope_own_only: Optional[bool] = True
```

**Response** (200 OK):
```json
{
  "role_id": "role-uuid",
  "role_name": "hotel_manager",
  "resources": [
    {
      "resource": "hotels",
      "can_create": true,
      "can_read": true,
      "can_update": true,
      "can_delete": false
    }
  ],
  "scope_own_only": true,
  "updated_at": "2024-01-16T14:30:00Z"
}
```

**Error Responses**:
- `404 Not Found`: Role not found
- `400 Bad Request`: Invalid permissions format
- `403 Forbidden`: Cannot modify system roles

---

## 4. User-Role Assignment

### GET /user-roles

List all users with their assigned roles and resources.

**Authentication**: ✅ Required (Admin+)

**Request**:
```bash
GET /api/v1/admin/rbac/user-roles?page=1&page_size=20
Authorization: Bearer <token>
```

**Query Parameters**:
| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| page | int | 1 | Page number |
| page_size | int | 20 | Items per page |

**Response** (200 OK):
```json
{
  "items": [
    {
      "user_id": "user-uuid",
      "email": "manager@hotel.com",
      "full_name": "John Doe",
      "roles": [
        {
          "role_id": "role-uuid",
          "name": "hotel_manager",
          "label": "Hotel Manager"
        }
      ],
      "assigned_resources": {
        "hotels": [
          {
            "id": "hotel-uuid",
            "name": "Grand Plaza Hotel"
          }
        ],
        "apartments": [],
        "restaurants": []
      }
    }
  ],
  "total": 45,
  "page": 1,
  "page_size": 20,
  "total_pages": 3
}
```

**Response Schema**:
```python
class UserRoleResponse(BaseSchema):
    role_id: UUID
    name: str
    label: str

class ResourceItem(BaseSchema):
    id: UUID
    name: str

class AssignedResources(BaseSchema):
    hotels: List[ResourceItem]
    apartments: List[ResourceItem]
    restaurants: List[ResourceItem]

class UserWithRoleResponse(BaseSchema):
    user_id: UUID
    email: str
    full_name: str
    roles: List[UserRoleResponse]
    assigned_resources: AssignedResources
```

---

### POST /user-roles

Assign a role to a user.

**Authentication**: ✅ Required (Super Admin+)

**Request**:
```bash
POST /api/v1/admin/rbac/user-roles
Authorization: Bearer <token>
Content-Type: application/json

{
  "user_id": "user-uuid",
  "role_id": "role-uuid"
}
```

**Alternative (by email)**:
```json
{
  "email": "manager@hotel.com",
  "role_id": "role-uuid"
}
```

**Request Schema**:
```python
class UserRoleAssign(BaseSchema):
    user_id: Optional[UUID]
    email: Optional[str]  # Either user_id OR email required
    role_id: UUID
```

**Response** (201 Created):
```json
{
  "user_id": "user-uuid",
  "email": "manager@hotel.com",
  "full_name": "John Doe",
  "roles": [
    {
      "role_id": "role-uuid",
      "name": "hotel_manager",
      "label": "Hotel Manager"
    }
  ]
}
```

**Error Responses**:
- `400 Bad Request`: User not found, role not found, or already assigned
- `409 Conflict`: User already has this role
- `403 Forbidden`: Insufficient permissions

---

### DELETE /user-roles/{user_id}/{role_id}

Remove a role from a user.

**Authentication**: ✅ Required (Super Admin+)

**Request**:
```bash
DELETE /api/v1/admin/rbac/user-roles/{user_id}/{role_id}
Authorization: Bearer <token>
```

**Response** (204 No Content):
```
(empty body)
```

**Error Responses**:
- `404 Not Found`: User or role not found
- `400 Bad Request`: User does not have this role
- `403 Forbidden`: Insufficient permissions

---

### GET /users/{user_id}/resources

Get all resources (hotels, apartments, restaurants) assigned to a user by their manager role.

**Authentication**: ✅ Required (Admin+)

**Request**:
```bash
GET /api/v1/admin/rbac/users/{user_id}/resources
Authorization: Bearer <token>
```

**Response** (200 OK):
```json
{
  "user_id": "user-uuid",
  "email": "manager@hotel.com",
  "full_name": "John Doe",
  "role": "hotel_manager",
  "assigned_resources": {
    "hotels": [
      {
        "id": "hotel-uuid-1",
        "name": "Grand Plaza Hotel",
        "location": "New York"
      },
      {
        "id": "hotel-uuid-2",
        "name": "Riverside Resort",
        "location": "Miami"
      }
    ],
    "apartments": [],
    "restaurants": []
  }
}
```

---

## 5. Manager Availability

### GET /managers

Get list of available managers for assignment dialogs. Optionally filter by role.

**Authentication**: ✅ Required (Admin+)

**Request**:
```bash
GET /api/v1/admin/rbac/managers?role=hotel_manager
Authorization: Bearer <token>
```

**Query Parameters**:
| Parameter | Type | Description |
|-----------|------|-------------|
| role | string | Optional filter: `hotel_manager`, `apartment_manager`, `restaurant_manager` |

**Response** (200 OK):
```json
{
  "managers": [
    {
      "user_id": "user-uuid-1",
      "email": "john@company.com",
      "full_name": "John Doe",
      "role": "hotel_manager",
      "assigned_count": 3
    },
    {
      "user_id": "user-uuid-2",
      "email": "jane@company.com",
      "full_name": "Jane Smith",
      "role": "hotel_manager",
      "assigned_count": 2
    }
  ]
}
```

**Response Schema**:
```python
class ManagerResponse(BaseSchema):
    user_id: UUID
    email: str
    full_name: str
    role: str
    assigned_count: int

class ManagerListResponse(BaseSchema):
    managers: List[ManagerResponse]
```

---

## 6. Audit Logging

### GET /audit-logs

Retrieve audit logs of all RBAC changes with pagination.

**Authentication**: ✅ Required (Admin+)

**Request**:
```bash
GET /api/v1/admin/rbac/audit-logs?limit=50&offset=0
Authorization: Bearer <token>
```

**Query Parameters**:
| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| limit | int | 50 | Number of records to return |
| offset | int | 0 | Pagination offset |

**Response** (200 OK):
```json
{
  "logs": [
    {
      "id": "log-uuid",
      "actor_user_id": "admin-uuid",
      "actor_email": "admin@company.com",
      "action": "assign_role",
      "target_type": "user",
      "target_id": "user-uuid",
      "target_name": "John Doe",
      "meta_data": {
        "role_id": "role-uuid",
        "role_name": "hotel_manager",
        "old_roles": [],
        "new_roles": ["hotel_manager"]
      },
      "description": "Assigned role hotel_manager to user John Doe",
      "created_at": "2024-01-16T15:45:00Z"
    },
    {
      "id": "log-uuid-2",
      "actor_user_id": "admin-uuid",
      "actor_email": "admin@company.com",
      "action": "update_permissions",
      "target_type": "role",
      "target_id": "role-uuid",
      "target_name": "hotel_manager",
      "meta_data": {
        "old_permissions": {
          "hotels": {
            "can_create": false,
            "can_read": true,
            "can_update": false,
            "can_delete": false
          }
        },
        "new_permissions": {
          "hotels": {
            "can_create": false,
            "can_read": true,
            "can_update": true,
            "can_delete": false
          }
        }
      },
      "description": "Updated permissions for role hotel_manager",
      "created_at": "2024-01-16T14:30:00Z"
    }
  ],
  "total": 156,
  "limit": 50,
  "offset": 0
}
```

**Response Schema**:
```python
class AuditLogResponse(BaseSchema):
    id: UUID
    actor_user_id: Optional[UUID]
    actor_email: str
    action: str  # assign_role, remove_role, update_permissions, create_role, update_role, delete_role
    target_type: str  # user, role, hotel, apartment, restaurant
    target_id: UUID
    target_name: str
    meta_data: Dict[str, Any]
    description: str
    created_at: datetime

class AuditLogListResponse(BaseSchema):
    logs: List[AuditLogResponse]
    total: int
    limit: int
    offset: int
```

**Supported Actions**:
- `create_role` — New role created
- `update_role` — Role details updated
- `delete_role` — Role soft deleted
- `assign_role` — Role assigned to user
- `remove_role` — Role removed from user
- `update_permissions` — Role permissions changed

---

## Authentication & Error Handling

### Bearer Token Authentication

All endpoints require a Bearer token in the `Authorization` header:

```bash
Authorization: Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...
```

### Error Response Format

All errors follow a standard format:

```json
{
  "detail": "Error message here",
  "status_code": 400,
  "timestamp": "2024-01-16T15:30:00Z"
}
```

### HTTP Status Codes

| Code | Meaning |
|------|---------|
| 200 | OK — Request successful |
| 201 | Created — Resource created |
| 204 | No Content — Successful deletion |
| 400 | Bad Request — Invalid input |
| 401 | Unauthorized — Missing/invalid token |
| 403 | Forbidden — Insufficient permissions |
| 404 | Not Found — Resource not found |
| 409 | Conflict — Resource already exists |
| 500 | Server Error — Internal server error |

---

## Usage Examples

### Example 1: Create a New Role

```bash
curl -X POST http://localhost:8000/api/v1/admin/rbac/roles \
  -H "Authorization: Bearer <your-token>" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "content_editor",
    "label": "Content Editor",
    "description": "Edit website content and pages"
  }'
```

### Example 2: Update Role Permissions

```bash
curl -X PUT http://localhost:8000/api/v1/admin/rbac/roles/{role_id}/permissions \
  -H "Authorization: Bearer <your-token>" \
  -H "Content-Type: application/json" \
  -d '{
    "permissions": {
      "pages": {
        "can_create": true,
        "can_read": true,
        "can_update": true,
        "can_delete": false
      },
      "blogs": {
        "can_create": false,
        "can_read": true,
        "can_update": true,
        "can_delete": false
      }
    },
    "scope_own_only": true
  }'
```

### Example 3: Assign Role to User

```bash
curl -X POST http://localhost:8000/api/v1/admin/rbac/user-roles \
  -H "Authorization: Bearer <your-token>" \
  -H "Content-Type: application/json" \
  -d '{
    "email": "manager@hotel.com",
    "role_id": "550e8400-e29b-41d4-a716-446655440000"
  }'
```

### Example 4: Get Dashboard Statistics

```bash
curl -X GET http://localhost:8000/api/v1/admin/rbac/stats \
  -H "Authorization: Bearer <your-token>"
```

### Example 5: Retrieve Audit Logs

```bash
curl -X GET "http://localhost:8000/api/v1/admin/rbac/audit-logs?limit=20&offset=0" \
  -H "Authorization: Bearer <your-token>"
```

---

## System Roles

These roles cannot be modified or deleted:

| Role | Description |
|------|-------------|
| `super_admin` | Full system access, all permissions |
| `admin` | Administrative access, can manage roles and users |
| `doctor` | Doctor-specific access and consultations |
| `patient` | Patient profile and appointment access |

---

## Entity-Scoped Access

When a manager role is assigned to a user for a specific entity (hotel, apartment, restaurant):

1. User can only view/edit that entity
2. List endpoints automatically filter to show only assigned entities
3. Attempting to access another entity returns `403 Forbidden`
4. Changes are automatically logged to the audit trail

### Resource Manager Mapping

- **Hotel Manager** → Can manage assigned hotels and their bookings
- **Apartment Manager** → Can manage assigned apartments and their bookings
- **Restaurant Manager** → Can manage assigned restaurants and menu items

---

## Rate Limiting

All RBAC endpoints are rate-limited to:
- **100 requests per 60 seconds** per user

Exceeding this limit returns `429 Too Many Requests`.

---

## Integration Notes

### Automatic Filtering

When a manager makes API calls:
- `GET /admin/hotels` returns only their assigned hotels
- `GET /admin/apartments` returns only their assigned apartments
- `GET /admin/restaurants` returns only their assigned restaurants

### No Manual Filtering Needed

The backend automatically filters results based on the user's role and assigned resources. Managers cannot see or access other entities even with direct IDs.

### Audit Trail

Every RBAC operation (role creation, permission update, user assignment) is automatically logged with:
- Actor (admin making the change)
- Action type
- Target resource
- Old/new values
- Timestamp

---

## Next Steps

1. **Frontend Integration**: Implement RBAC dashboard UI with 4 tabs
2. **Database Migration**: Run migration for `rbac_audit_logs` table
3. **Testing**: Create integration tests for all endpoints
4. **Deployment**: Deploy to production server
5. **Monitoring**: Track audit logs for all RBAC changes

