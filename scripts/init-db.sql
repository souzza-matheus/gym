-- Cria os bancos adicionais necessários
-- (gymvision_users já é criado pelo POSTGRES_DB)
CREATE DATABASE gymvision_sessions;
GRANT ALL PRIVILEGES ON DATABASE gymvision_sessions TO gymvision;
