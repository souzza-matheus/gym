-- V3__fix_demo_password_hash.sql
-- O hash bcrypt usado em V1 para os usuários de demo NÃO corresponde à senha
-- documentada no comentário ("gymvision123") — é o hash de exemplo clássico
-- de tutoriais do Spring Security/jBCrypt para a senha "secret". Isso fazia
-- o login com a senha documentada falhar sempre ("Credenciais inválidas"),
-- inclusive impedindo carregar o perfil no app (e, por consequência, a tela
-- de logout, que só aparece após o perfil carregar com sucesso).
--
-- Hash novo gerado de fato para "gymvision123" (bcrypt, 10 rounds).
UPDATE users
SET password = '$2b$10$oFRROSFvl4J5eloWVWo4rOMjT4DZv7hVvTgkT2wINCXVzFk88vcAy'
WHERE email IN ('admin@gymvision.com', 'professor@gymvision.com', 'joao@gymvision.com');
