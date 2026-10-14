# simulacao-tributacao-imobiliaria
O debate no mundo atual frequentemente esbarra na pergunta: "Como baratear o mercado imobiliário?". Como economista, entendo que o nosso papel é analisar e desenhar os incentivos da sociedade para atingir objetivos que tragam bem-estar geral. Além disso, é nosso dever humano agir com justiça, tratando os desiguais com pesos distintos, o que naturalmente se cruza com a política de impostos.

O simulador já disponível: 
https://simulacao-tributacao-imobiliaria-eupaqmdvdyvcqoh3kdkxwk.streamlit.app/?

Essa é a minha primeira tentativa no desbravar da politica tributária, muito inspirado pelo autor Rodrigo Orair, que conheci pessoalmente em um dos congressos da Feneco. Esse projeto tende a vir a ser, o meu primeiro projeto de pesquisa na Universidade de São Paulo, onde tentarei propor uma politica mais equilibrada seguindo o preceito de progressividade tributária, assunto esse esvaziado no cenário de debate publico atual, envolvendo-se intimamente com outras pautas, estas mais voga que são a organização fundiária, direito de moradia e gentrificação. Barcelona, Rio de Janeiro e até mesmo EUA ou China tem sofrido desse malus que assola a minha geração, a falta de acesso a casa própria, muitas vezes causada pela má distribuição de riquezas acumuladas nos últimos 56 anos. 

Em decorrência disso, a minha geração necessita não só levantar esse problema, mas participar do debate de como solucioná-lo, pois nada adianta resolvermos a situação para nós, e as gerações seguintes entrarem na mesma espiral destrutiva.

Como a primeira fagulha de incitar esse debate, observando meus colegas no debate, senti a necessidade de "Desenhar para as pessoas entenderem", desta forma apropriei-me dos conhecimentos acumulados no meu trabalho no Itaú para desenhar esse simulador, para que qualquer um, direita, esquerda ou centro, possa brincar com os princípios de progressividade. Trazendo não só a tributação mas também o desenho do mercado que será manipulado, e com a personalização como core central do projeto, qualquer um (sem necessidade de noções de programação) pode testar um pouco das três propostas/modelos apresentados no trabalho.

A Matemática da Progressividade: Entendendo a Fórmula:

O núcleo deste simulador baseia-se numa equação que ajusta a carga tributária de cada imóvel considerando não apenas o seu valor isolado, mas a sua relação com o mercado local e a concentração de riqueza do proprietário. 

A fórmula aplicada é:

$$Imposto = V \times T_{base} \times \left(\frac{V}{M}\right)^P \times G^{(N-1)}$$

Onde cada variável representa um mecanismo de incentivo econômico:

* **$V$ (Valor do Imóvel):** O valor de mercado da propriedade analisada.
* **$T_{base}$ (Alíquota Base):** A taxa de referência do imposto (derivada do *yield* praticado no mercado).
* **$M$ (Valor Mediano dos Imóveis):** O valor de referência que divide o mercado ao meio. Funciona como a "âncora" da função social.
* **$P$ (Fator de Progressividade):** O expoente que define a curvatura do imposto. Quanto maior o $P$, mais íngreme é a cobrança para imóveis de luxo.
* **$N$ (Quantidade de Imóveis do Proprietário):** Quantas propriedades a mesma pessoa possui.
* **$G$ (Fator de Acúmulo):** O multiplicador de penalidade por concentração fundiária.

**Como os três pilares funcionam na prática:**

1. **A Base ($V \times T_{base}$):** Calcula o imposto linear padrão, como é feito na maioria dos sistemas tributários atuais.

2. **A Função Social $\left(\frac{V}{M}\right)^P$:** Controla a distribuição. Se o imóvel for mais barato que a mediana da cidade ($V < M$), este bloco resulta num número menor que 1, concedendo um **desconto** ao proprietário. Se for mais caro ($V > M$), atua como um multiplicador progressivo, taxando o alto padrão com maior peso.

3. **O Acúmulo Patrimonial $G^{(N-1)}$:** Controla a concentração fundiária e a gentrificação. Se a pessoa tem apenas uma casa ($N = 1$), o expoente torna-se zero ($G^0 = 1$), e **não há penalidade**. A partir do segundo imóvel, a carga tributária multiplica-se progressivamente, desincentivando a retenção especulativa de propriedades.


A Fórmula da Função Social (O Desconto):

A Função Social não é apenas uma ideia abstrata; no nosso modelo, ela ganha uma fórmula própria que atua diretamente para aliviar o peso sobre quem tem menos, e atuando principalmente no futuro da nossa pesquisa, tentar amenizar o impacto da tributação em propriedades para pessoas de baixa renda, criando um incentivo para a manutenção de alugueis baratos para a população. Essa é uma alternativa, ainda não muito explorada que carece de atenção.

A equação base para o cálculo deste desconto é:

$$D_{social} = \alpha \times \frac{Y_{ref} - Y_{real}}{Y_{ref}}$$

**O que isto significa na prática?**

Quando o imóvel está **abaixo** do valor mediano da cidade (ou seja, quando o *Yield Real Praticado* — $Y_{real}$ — fica acima do *Yield de Referência* — $Y_{ref}$), a equação gera um multiplicador positivo. Este multiplicador converte-se num **desconto financeiro** no imposto final, subsidiando a base do mercado e incentivando o acesso à moradia.

Por outro lado, quando o imóvel está muito acima da mediana (um imóvel de luxo, por exemplo), a métrica fica "Fora dos Critérios", resultando num desconto de **$0,0000 = 0$**. Neste cenário, a Função Social desliga-se e a progressividade entra em ação com todo o seu peso.
