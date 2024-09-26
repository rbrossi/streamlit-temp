import streamlit as st
import pandas as pd
import plotly.express as px

# Page settings
st.set_page_config(
    page_title='Calculadora IMA-B',
    layout="wide",
    initial_sidebar_state="expanded",
)

st.title('Calculadora IMAB')
col1, col2, col3 = st.columns(3)

def get_data(url, options):

    ima_components = pd.read_parquet(url)
    ntnb_data = ima_components.query('index_name in @options')
    ntnb_data['mod_duration'] = ntnb_data['duration'] / 252
    ntnb_data['DV01'] = ntnb_data['mod_duration'] * ntnb_data['weight']

    return ntnb_data


def optimize_portfolio(selected_data, selection, invested_value):

    ### Bug = IMAB5 está alocando em 2030 ao invés de 2028

    optimized_short_term = selected_data.query('maturity < 2028')
    optimized_mid_term = selected_data.query('maturity >= 2028 and maturity < 2035')
    optimized_long_term = selected_data.query('maturity >= 2035')

    short_term_maturity = '2026-08-15'

    if selection == 'imab5':
        mid_term_maturity = '2028-08-15'
    else:
        mid_term_maturity = '2030-08-15'

    long_term_maturity_1 = '2035-05-15'
    long_term_maturity_2 = '2050-08-15'

    long_term_maturities_sum = selected_data.query('maturity == @long_term_maturity_1 or maturity == @long_term_maturity_2')['mod_duration'].sum()
    long_term_mod_duration_1 = selected_data.query('maturity == @long_term_maturity_1')['mod_duration'].sum() / long_term_maturities_sum
    long_term_mod_duration_2 = selected_data.query('maturity == @long_term_maturity_2')['mod_duration'].sum() / long_term_maturities_sum

    optimized_portfolio = pd.DataFrame({
        'ticker': [f'NTN-B {short_term_maturity[:7]}',
                   f'NTN-B {mid_term_maturity[:7]}',
                   f'NTN-B {long_term_maturity_1[:7]}',
                   f'NTN-B {long_term_maturity_2[:7]}'],
        'Novos pesos': [optimized_short_term['weight'].sum(),
                        optimized_mid_term['weight'].sum(),
                        long_term_mod_duration_1 * optimized_long_term['weight'].sum(),
                        long_term_mod_duration_2 * optimized_long_term['weight'].sum()],
        'Nova alocação': [invested_value * optimized_short_term['weight'].sum(),
                          invested_value * optimized_mid_term['weight'].sum(),
                          invested_value * (long_term_mod_duration_1 * optimized_long_term['weight'].sum()),
                          invested_value * (long_term_mod_duration_2 * optimized_long_term['weight'].sum())]
    }).query('`Novos pesos` > 0')

    return optimized_portfolio

imab_options_box = ['IMA-B 5', 'IMA-B', 'IMA-B 5+']
imab_options = ['imab5', 'imab', 'imab5+']
selected_index = col1.selectbox('Selecione o índice:', imab_options_box)
if selected_index == 'IMA-B 5':
    selection = 'imab5'
elif selected_index == 'IMA-B':
    selection = 'imab'
else:
    selection = 'imab5+'

ntnb_data = get_data('ima_components.parquet', imab_options)

selected_data = ntnb_data.query('index_name == @selection')
#selected_data['ticker'] = selected_data['index_name'].str.upper() + ' ' + selected_data['bond_ticker'].apply(lambda x: x.split('_')[-1][:7])
selected_data['ticker'] = 'NTN-B ' + selected_data['bond_ticker'].apply(lambda x: x.split('_')[-1][:7])
selected_data['ntnb_weight'] = selected_data['weight'] * 100
selected_data['invested_value'] = 0

current_portfolio = col1.data_editor(selected_data[['ticker', 'invested_value']],
                                     disabled=['ticker'],
                                     hide_index=True,
                                     width=800,
                                     column_config=dict(
                                         weight=st.column_config.NumberColumn('NTNB Weight', format='%.2f%%'))
                                     )
selected_data['invested_value'] = current_portfolio['invested_value']
selected_data['portfolio_weight'] = selected_data['invested_value'] / selected_data['invested_value'].sum()
selected_data['portfolio_DV01'] = selected_data['mod_duration'] * selected_data['portfolio_weight']
selected_data['maturity'] = pd.to_datetime(selected_data['maturity'])

optimized_portfolio = optimize_portfolio(selected_data, selection, current_portfolio["invested_value"].sum())

imab_yield = sum(selected_data['rate'] * selected_data['weight'])
portfolio_yield = sum(selected_data['rate'] * selected_data['portfolio_weight'])

merged_optimized_portfolio = selected_data.query('ticker in @optimized_portfolio.ticker').merge(optimized_portfolio, left_on='ticker', right_on='ticker')
merged_optimized_portfolio['optimized_dv01'] = merged_optimized_portfolio['mod_duration'] * merged_optimized_portfolio['Novos pesos']
optimized_portfolio_yield = sum(merged_optimized_portfolio['rate'] * merged_optimized_portfolio['Novos pesos'])
optimized_portfolio_dv01 = merged_optimized_portfolio['optimized_dv01'].sum()

merged_selected_data = selected_data.merge(optimized_portfolio, on='ticker', how='left')
#merged_selected_data = current_portfolio.merge(merged_selected_data, on='ticker', how='left')
merged_selected_data['optimized_dv01'] = merged_selected_data['mod_duration'] * merged_selected_data['Novos pesos']

col2.subheader(f'Portfólio {selected_index}')

fig = px.pie(selected_data, values='ntnb_weight', names='ticker')
fig.update_layout(
    width=600,
    height=400
)
col2.plotly_chart(fig)

if selected_data['invested_value'].sum() > 0:

    col1.write(f'PL: $ {current_portfolio["invested_value"].sum():,.2f}')

    col1.subheader('DV1')
    col1.table(pd.DataFrame({
        'Metric': [f'{selected_index}', 'Portfólio atual', 'Portfólio Otimizado'],
        'Value': [
            f'$ {selected_data["DV01"].sum() / 10:.2f}',
            f'$ {selected_data["portfolio_DV01"].sum() / 10:.2f}',
            f'$ {optimized_portfolio_dv01 / 10:.2f}',
        ]
    })
    )

    col1.subheader('Duration')
    col1.table(pd.DataFrame({
        'Metric': [f'{selected_index}', 'Portfólio atual', 'Portfólio Otimizado'],
        'Value': [
            f'{round(selected_data["DV01"].sum(), 2)}',
            f'{round(selected_data["portfolio_DV01"].sum(), 2)}',
            f'{round(optimized_portfolio_dv01, 2)}'
        ]
    })
    )

    col1.subheader('Yield')
    col1.table(pd.DataFrame({
        'Metric': [f'{selected_index} ', 'Portfólio atual', 'Portfólio Otimizado'],
        'Value': [
            f'{imab_yield:.1%}',
            f'{portfolio_yield:.1%}',
            f'{optimized_portfolio_yield:.1%}',
        ]
    })
    )

    col3.subheader(f'Portfólio atual')
    fig = px.pie(current_portfolio.query('invested_value > 0'), values='invested_value', names='ticker')
    fig.update_layout(
        width=600,
        height=400
    )
    col3.plotly_chart(fig)

    col2.subheader('Portfólio Otimizado')
    fig = px.pie(optimized_portfolio, values='Novos pesos', names='ticker')
    fig.update_layout(
        width=600,
        height=400
    )
    col2.plotly_chart(fig)

    col3.subheader('Novas alocações')
    col3.table(optimized_portfolio)


    # Yield (IPCA+) vs Duration
    yield_vs_duration = pd.DataFrame({
        'Portfólio': [selected_index, 'Portfólio atual', 'Portfólio Otimizado'],
        'Yield': [imab_yield, portfolio_yield, optimized_portfolio_yield],
        'Duration': [selected_data['DV01'].sum(), selected_data['portfolio_DV01'].sum(), optimized_portfolio_dv01]
    })

    col3.subheader('Yield vs Duration')
    fig = px.scatter(yield_vs_duration, x='Duration', y='Yield', color='Portfólio')
    fig.update_layout(
        xaxis_title='Duration',
        yaxis_title='Yield',
        yaxis_tickformat='.2%',
        yaxis=dict(range=[0.03, 0.09]),
        legend=dict(y=1.1, orientation='h')
    )
    col3.plotly_chart(fig)

    st.subheader('DV01 por vértice')
    melted = merged_selected_data[['ticker', 'portfolio_DV01', 'DV01', 'optimized_dv01']].melt(id_vars='ticker', value_vars=['DV01', 'portfolio_DV01', 'optimized_dv01'])
    fig = px.bar(melted, x="value", y="variable", color='ticker',
                 height=400, width=800)
    fig.update_layout(
        legend=dict(y=1.1, orientation='h')
    )

    st.plotly_chart(fig)

    fig = px.bar(merged_selected_data, x='ticker', y=['DV01', 'portfolio_DV01', 'optimized_dv01'],
                 barmode='group', height=400, width=800)
    fig.update_layout(
        legend=dict(y=1.1, orientation='h')
    )
    st.plotly_chart(fig)


st.subheader(selected_index)
st.dataframe(selected_data[['ticker', 'price', 'duration', 'mod_duration', 'convexity', 'rate', 'DV01', 'weight']],
             hide_index=True,
             width=1400,
             )
