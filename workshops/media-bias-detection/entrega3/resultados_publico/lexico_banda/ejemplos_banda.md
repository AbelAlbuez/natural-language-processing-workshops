# Ejemplos: el mismo hecho contado distinto (banda 0,65–0,80, filtrada)

Titulares reconstruidos desde la URL (sin tildes, cifras ni puntuación). Cada tabla es una pareja recíproca
de dos medios con similitud 0,65–0,80 que pasa el filtro (misma fecha + ≥ 1 término(s) compartido(s) que aparece(n) en ≤ 1.000 titulares del corpus).
**El filtro acierta el mismo hecho en el 81 % de las parejas anotadas que pasan (IC 95 % 57–93 %)**: alguna pareja de esta lista puede ser
dos hechos distintos. Semilla 42.

## 1. Parejas anotadas a mano que pasan el filtro

Todas las parejas de la calibración en la banda que pasan el filtro, con la etiqueta de la anotación. Sirven
para ver qué clase de errores deja pasar.

| Sim. | Días | Etiqueta | Titular A | Titular B |
|---:|---:|---|---|---|
| 0,67 | 0 | Mismo hecho | Buscan mil hogares que no han cobrado renta ciudadana y devolucion del iva link para consultar | Atencion mas de hogares aun no reclaman renta ciudadana y devolucion del iva |
| 0,68 | 0 | Distinto | Embajador plata pide perdon por polemica de escritores no invitados a la feria del libro de madrid | Luis guillermo plata me equivoque embajador pide perdon por mal uso de la palabra neutro |
| 0,71 | 0 | Mismo hecho | Grupo de victimas de harvey weinstein seria indemnizado con cerca de millones de dolares | Harvey wenstein debera pagar millones de dolares a victimas de abuso |
| 0,71 | 0 | Mismo tema / otro hecho | Presidente de uruguay tampoco asistira a cumbre de las americas por que | Presidente de mexico confirmo que no asistira a la cumbre de las americas en ee uu |
| 0,72 | 0 | Mismo hecho | Eln asesina a tres soldados dos de ellos murieron por un ataque con dron | Ataque con dron del eln deja dos soldados muertos y cuatro heridos en el sur de bolivar confirma el ejercito nacional |
| 0,73 | 0 | Mismo tema / otro hecho | El mensaje de marta lucia ramirez al nuevo canciller alvaro leyva | Canciller marta lucia ramirez lista para empalme con su sucesor alvaro leyva |
| 0,74 | 0 | Mismo hecho | Este es el parte de salud de los cuatro soldados atacados por el eln en valdivia antioquia | Hostigamientos contra la fuerza publica deja cuatro soldados heridos continua el temor en valdivia antioquia |
| 0,77 | 0 | Mismo hecho | Plenarias de camara y senado aprueban ley de aumento de cupo de endeudamiento gobierno petro no entara en default | Camara de representantes aprobo ampliacion de cupo de endeudamiento |
| 0,77 | 0 | Mismo hecho | Que opina de los ratones que fueron lanzados en el congreso | Centro democratico autorizo entrada de sospechosos de lanzar ratones a su bancada |
| 0,78 | 0 | Mismo hecho | Procuraduria investiga a contratistas por posibles fallas en construccion del puente hisgaura | Procuraduria investiga irregularidades en construccion de polemico puente en santander |
| 0,78 | 0 | Mismo hecho | German vargas lleras hace un llamado para armar coalicion opositora | La coalicion que convoca german vargas lleras se arma desde la semana pasada en casa de cesar gaviria |
| 0,78 | 0 | Mismo hecho | Francisco sagasti elegido nuevo presidente de peru | Francisco sagasti gana mesa directa y sera presidente de peru hasta el de julio de |
| 0,78 | 0 | Mismo hecho | Futbol colombiano fifa y gobierno se ponen las pilas para mejorar condiciones labores | Fifa y gobierno de colombia hacen acuerdos por futbolistas |
| 0,79 | 0 | Mismo hecho | Corte suprema avalo la extradicion de alias otoniel a estados unidos | Atencion corte suprema dio su aval para la extradicion de otoniel |
| 0,79 | 0 | Mismo hecho | Impuesto al patrimonio de nueva emergencia economica afectara a empresas | Como podria afectar el bolsillo de las personas el nuevo impuesto al patrimonio que pagaran las grandes empresas |
| 0,80 | 0 | Mismo hecho | Un policia asesinado y otro herido en ataque armado en tuchin cordoba | Matan a un policia y dejan otro herido en tuchin cordoba |

## 2. Palabras distintivas nuevas (no salían con ≥ 0,80)

Para cada medio y gobierno, hasta dos términos de contenido distintivos y robustos en la banda filtrada
que en los eventos ≥ 0,80 no eran ni siquiera significativos (z < 1,96), y una pareja en la que el medio usa el término y el otro
medio no.

### Gobierno Duque

*El Tiempo · «ivan duque»*: 2,4 % de sus titulares frente al 1,0 % del otro medio (log-odds +0,88, z 4,1; ≥ 0,80: z 1,6) (también separa al medio en las parejas rechazadas: posible rasgo de la casa).

**Pareja 2002** · 2019-06-11 · similitud 0,77

| Medio | Titular |
|---|---|
| **El Tiempo** | Que piensa el presidente ivan duque sobre la posesion de jesus santrich |
| Blu Radio | Jesus santrich se posesiono como representante a la camara |

### Gobierno Petro

*El Tiempo · «colombia»*: 4,7 % de sus titulares frente al 3,4 % del otro medio (log-odds +0,32, z 4,6; ≥ 0,80: z 0,8) (también separa al medio en las parejas rechazadas: posible rasgo de la casa).

**Pareja 43872** · 2025-07-29 · similitud 0,76

| Medio | Titular |
|---|---|
| **El Tiempo** | Embajada de colombia en estados unidos responde oficialmente a postura del secretario de estado marco rubio sobre caso uribe |
| Noticias RCN | Gobierno colombiano respondio a marco rubio sobre caso uribe |

*El Tiempo · «cepeda»*: 0,8 % de sus titulares frente al 0,4 % del otro medio (log-odds +0,65, z 3,9; ≥ 0,80: z 1,8) (también separa al medio en las parejas rechazadas: posible rasgo de la casa).

**Pareja 39102** · 2024-03-04 · similitud 0,73

| Medio | Titular |
|---|---|
| **El Tiempo** | Tendran control desde el gobierno y desde la oposicion cepeda sobre nombramientos |
| Noticias RCN | Debe haber control institucional dilian francisca toro al gobierno sobre disidencias en jamundi |

## 3. «Gobierno Petro/Duque» frente a «el Gobierno» en la misma pareja

Parejas domésticas filtradas en las que un medio escribe el apellido del presidente junto a «Gobierno» y
el otro escribe «Gobierno» o «Gobierno nacional» sin él.

### Gobierno Duque (9 parejas con los dos usos)

**Pareja 30744** · 2020-09-01 · similitud 0,74

| Medio | Titular |
|---|---|
| El Tiempo | Como es la polemica por prestamo del gobierno a avianca |
| Noticias Caracol | Vamos a pagar presidente de avianca habla del polemico prestamo otorgado por el gobierno duque |

**Pareja 47662** · 2018-11-23 · similitud 0,69

| Medio | Titular |
|---|---|
| Noticias Caracol | Resolver problemas de electricaribe es una obsesion para el gobierno ivan duque |
| La República | Gobierno buscara solucion integral para electricaribe e invertira millones |

**Pareja 672** · 2018-11-07 · similitud 0,67

| Medio | Titular |
|---|---|
| Blu Radio | Cual es el balance de los tres primeros meses del gobierno duque |
| Noticias Caracol | Este es el balance que hace duque en sus primeros dias de gobierno |

**Pareja 48964** · 2022-07-26 · similitud 0,71

| Medio | Titular |
|---|---|
| Noticias RCN | Gobierno actual reglamento impuesto por valorizacion quienes deben pagarlo |
| La República | Quienes pagaran el nuevo impuesto por valorizacion que deja el gobierno duque |

### Gobierno Petro (110 parejas con los dos usos)

**Pareja 37478** · 2023-09-02 · similitud 0,78

| Medio | Titular |
|---|---|
| El Tiempo | Gobierno petro y disidencias de ivan mordisco logran acuerdo para dialogos de paz |
| Noticias Caracol | Gobierno y disidencias de las farc de ivan mordisco logran acuerdo para instalar una mesa de dialogo |

**Pareja 10720** · 2022-09-07 · similitud 0,74

| Medio | Titular |
|---|---|
| Blu Radio | Rebaja de las tarifas de la luz sera gradual no podemos esperar un cambio abrupto gobierno |
| Noticias Caracol | Gobierno petro dice que tarifas de la luz se reduciran gradualmente y no de forma abrupta |

**Pareja 41776** · 2024-12-16 · similitud 0,69

| Medio | Titular |
|---|---|
| El Tiempo | Recorte a los recursos de los congresistas y otras posibilidades que baraja el gobierno petro tras hundimiento de la tributaria |
| La República | El recorte que debe hacer el gobierno para cumplir con la regla fiscal |

**Pareja 46632** · 2026-04-28 · similitud 0,75

| Medio | Titular |
|---|---|
| El Tiempo | Gobierno petro rechazo suspension del consejo de estado al decreto de traslado expres de ahorro pensional a colpensiones no es admisible |
| Noticias RCN | Gobierno reacciona a suspension del decreto que ordenaba el traslado de billones de las afp a colpensiones |

## 4. Misma entidad, otra redacción

Parejas filtradas con el menor solapamiento de las palabras no raras (Jaccard ≤ 0,10): comparten el
nombre propio o el lugar, pero el resto del titular es distinto. Ocho al azar.

**Pareja 48524** · 2021-06-28 · similitud 0,78

| Medio | Titular |
|---|---|
| Noticias Caracol | Pilas pensionado vea como actualizar el rut para que se evite lios con la dian |
| La República | La dian actualizo las actividades economicas del rut de pensionados |

**Pareja 47315** · 2026-07-14 · similitud 0,70

| Medio | Titular |
|---|---|
| El Tiempo | Es viable que el presidente electo abelardo de la espriella se posesione en una guarnicion militar esto dicen los expertos |
| Noticias RCN | Rodrigo lara ministro del designado reitero que posesion presidencial sera en guarnicion militar |

**Pareja 20687** · 2025-01-08 · similitud 0,78

| Medio | Titular |
|---|---|
| El Tiempo | Detuvieron al excandidato presidencial enrique marquez en venezuela segun denuncio el partido opositor vp |
| Blu Radio | Regimen de maduro detuvo al excandidato presidencial enrique marquez |

**Pareja 10038** · 2022-07-08 · similitud 0,78

| Medio | Titular |
|---|---|
| El Tiempo | Quien es luis ernesto vargas el nuevo embajador de petro ante la oea |
| Blu Radio | Habra compromiso real con la paz no uno aparente luis ernesto vargas embajador designado ante oea |

**Pareja 35359** · 2022-11-30 · similitud 0,69

| Medio | Titular |
|---|---|
| El Tiempo | Anif pide mesura en la discusion del salario minimo |
| Noticias Caracol | Se inicio la discusion del salario minimo que se logro en esta primera reunion |

**Pareja 44656** · 2025-10-19 · similitud 0,80

| Medio | Titular |
|---|---|
| El Tiempo | Bolivia elige presidente entre dos candidatos de derecha que prometen superar crisis economica y romper con aislamiento trump y milei serian claves |
| Noticias RCN | El panorama politico en bolivia en medio de unas elecciones decisivas |

**Pareja 6026** · 2021-03-11 · similitud 0,78

| Medio | Titular |
|---|---|
| Blu Radio | Aranceles a los textiles aumentara el contrabando fenalco |
| La República | Contrabando de prendas podria tener un margen de con los nuevos aranceles |

**Pareja 6725** · 2021-06-10 · similitud 0,72

| Medio | Titular |
|---|---|
| El Tiempo | Emma coronel de que se declarara culpable en estados unidos |
| Blu Radio | Emma coronel esposa del chapo se declara culpable de narcotrafico en eeuu |
