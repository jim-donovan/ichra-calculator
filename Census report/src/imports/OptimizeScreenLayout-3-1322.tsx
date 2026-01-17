function Heading() {
  return (
    <div className="h-[48px] relative shrink-0 w-[374.406px]" data-name="Heading 1">
      <div className="bg-clip-padding border-0 border-[transparent] border-solid relative size-full">
        <p className="absolute css-ew64yg font-['Inter:Bold',sans-serif] font-bold leading-[48px] left-0 not-italic text-[#115e59] text-[32px] top-[-0.5px]">Census Analysis Report</p>
      </div>
    </div>
  );
}

function Text() {
  return (
    <div className="h-[42px] relative shrink-0 w-[75.781px]" data-name="Text">
      <div className="bg-clip-padding border-0 border-[transparent] border-solid relative size-full">
        <p className="absolute css-ew64yg font-['Inter:Light',sans-serif] font-light leading-[42px] left-0 not-italic text-[#6b7280] text-[28px] top-0">Client</p>
      </div>
    </div>
  );
}

function Container() {
  return (
    <div className="absolute content-stretch flex h-[66px] items-center justify-between left-[48px] pb-[2px] pt-0 px-0 top-[48px] w-[1824px]" data-name="Container">
      <div aria-hidden="true" className="absolute border-[#0f766e] border-b-2 border-solid inset-0 pointer-events-none" />
      <Heading />
      <Text />
    </div>
  );
}

function Paragraph() {
  return (
    <div className="h-[21px] relative shrink-0 w-full" data-name="Paragraph">
      <p className="absolute css-ew64yg font-['Poppins:SemiBold',sans-serif] leading-[21px] left-[219.39px] not-italic text-[#6b7280] text-[14px] text-center top-[0.5px] translate-x-[-50%]">TOTAL EMPLOYEES</p>
    </div>
  );
}

function Paragraph1() {
  return (
    <div className="h-[48px] relative shrink-0 w-full" data-name="Paragraph">
      <p className="absolute css-ew64yg font-['Poppins:Regular',sans-serif] leading-[48px] left-[219.28px] not-italic text-[#111827] text-[48px] text-center top-[2px] translate-x-[-50%]">49</p>
    </div>
  );
}

function MetricCard() {
  return (
    <div className="col-[1] content-stretch css-vsca90 flex flex-col gap-[8px] items-start relative row-[1] self-stretch shrink-0" data-name="MetricCard">
      <Paragraph />
      <Paragraph1 />
    </div>
  );
}

function Paragraph2() {
  return (
    <div className="h-[21px] relative shrink-0 w-full" data-name="Paragraph">
      <p className="absolute css-ew64yg font-['Poppins:SemiBold',sans-serif] leading-[21px] left-[219.48px] not-italic text-[#6b7280] text-[14px] text-center top-[0.5px] translate-x-[-50%]">TOTAL DEPENDENTS</p>
    </div>
  );
}

function Paragraph3() {
  return (
    <div className="h-[48px] relative shrink-0 w-full" data-name="Paragraph">
      <p className="absolute css-ew64yg font-['Poppins:Regular',sans-serif] leading-[48px] left-[219.22px] not-italic text-[#111827] text-[48px] text-center top-[2px] translate-x-[-50%]">14</p>
    </div>
  );
}

function MetricCard1() {
  return (
    <div className="col-[2] content-stretch css-vsca90 flex flex-col gap-[8px] items-start relative row-[1] self-stretch shrink-0" data-name="MetricCard">
      <Paragraph2 />
      <Paragraph3 />
    </div>
  );
}

function Paragraph4() {
  return (
    <div className="h-[21px] relative shrink-0 w-full" data-name="Paragraph">
      <p className="absolute css-ew64yg font-['Poppins:SemiBold',sans-serif] leading-[21px] left-[219.41px] not-italic text-[#6b7280] text-[14px] text-center top-[0.5px] translate-x-[-50%]">COVERED LIVES</p>
    </div>
  );
}

function Paragraph5() {
  return (
    <div className="h-[48px] relative shrink-0 w-full" data-name="Paragraph">
      <p className="absolute css-ew64yg font-['Poppins:Regular',sans-serif] leading-[48px] left-[219.12px] not-italic text-[#111827] text-[48px] text-center top-[2px] translate-x-[-50%]">63</p>
    </div>
  );
}

function MetricCard2() {
  return (
    <div className="col-[3] content-stretch css-vsca90 flex flex-col gap-[8px] items-start relative row-[1] self-stretch shrink-0" data-name="MetricCard">
      <Paragraph4 />
      <Paragraph5 />
    </div>
  );
}

function Paragraph6() {
  return (
    <div className="h-[21px] relative shrink-0 w-full" data-name="Paragraph">
      <p className="absolute css-ew64yg font-['Poppins:SemiBold',sans-serif] leading-[21px] left-[219.16px] not-italic text-[#6b7280] text-[14px] text-center top-[0.5px] translate-x-[-50%]">STATES</p>
    </div>
  );
}

function Paragraph7() {
  return (
    <div className="h-[48px] relative shrink-0 w-full" data-name="Paragraph">
      <p className="absolute css-ew64yg font-['Poppins:Regular',sans-serif] leading-[48px] left-[219.31px] not-italic text-[#111827] text-[48px] text-center top-[2px] translate-x-[-50%]">1</p>
    </div>
  );
}

function MetricCard3() {
  return (
    <div className="col-[4] content-stretch css-vsca90 flex flex-col gap-[8px] items-start relative row-[1] self-stretch shrink-0" data-name="MetricCard">
      <Paragraph6 />
      <Paragraph7 />
    </div>
  );
}

function Container1() {
  return (
    <div className="absolute gap-[24px] grid grid-cols-[repeat(4,_minmax(0,_1fr))] grid-rows-[repeat(1,_minmax(0,_1fr))] h-[109px] left-[48px] pb-[32px] pt-0 px-0 top-[146px] w-[1824px]" data-name="Container">
      <MetricCard />
      <MetricCard1 />
      <MetricCard2 />
      <MetricCard3 />
    </div>
  );
}

function Paragraph8() {
  return (
    <div className="h-[21px] relative shrink-0 w-full" data-name="Paragraph">
      <p className="absolute css-ew64yg font-['Poppins:SemiBold',sans-serif] leading-[21px] left-[293.55px] not-italic text-[#6b7280] text-[14px] text-center top-[0.5px] translate-x-[-50%]">AVG AGE OF COVERED LIVES</p>
    </div>
  );
}

function Paragraph9() {
  return (
    <div className="h-[48px] relative shrink-0 w-[99.031px]" data-name="Paragraph">
      <div className="bg-clip-padding border-0 border-[transparent] border-solid relative size-full">
        <p className="absolute css-ew64yg font-['Poppins:Regular',sans-serif] leading-[48px] left-[50.5px] not-italic text-[#111827] text-[48px] text-center top-[2px] translate-x-[-50%]">34.6</p>
      </div>
    </div>
  );
}

function Paragraph10() {
  return (
    <div className="h-[28px] relative shrink-0 w-[30px]" data-name="Paragraph">
      <div className="bg-clip-padding border-0 border-[transparent] border-solid relative size-full">
        <p className="absolute css-ew64yg font-['Poppins:Medium',sans-serif] leading-[20px] left-[15px] not-italic text-[#6b7280] text-[20px] text-center top-px translate-x-[-50%]">yrs</p>
      </div>
    </div>
  );
}

function Container2() {
  return (
    <div className="h-[48px] relative shrink-0 w-full" data-name="Container">
      <div className="flex flex-row items-end justify-center size-full">
        <div className="content-stretch flex gap-[8px] items-end justify-center pl-0 pr-[0.008px] py-0 relative size-full">
          <Paragraph9 />
          <Paragraph10 />
        </div>
      </div>
    </div>
  );
}

function MetricCardWithUnit() {
  return (
    <div className="absolute content-stretch flex flex-col gap-[8px] h-[77px] items-start left-0 top-0 w-[586.664px]" data-name="MetricCardWithUnit">
      <Paragraph8 />
      <Container2 />
    </div>
  );
}

function Paragraph11() {
  return (
    <div className="h-[21px] relative shrink-0 w-full" data-name="Paragraph">
      <p className="absolute css-ew64yg font-['Poppins:SemiBold',sans-serif] leading-[21px] left-[293.78px] not-italic text-[#6b7280] text-[14px] text-center top-[0.5px] translate-x-[-50%]">MEDIAN AGE OF COVERED LIVES</p>
    </div>
  );
}

function Paragraph12() {
  return (
    <div className="h-[48px] relative shrink-0 w-[98.641px]" data-name="Paragraph">
      <div className="bg-clip-padding border-0 border-[transparent] border-solid relative size-full">
        <p className="absolute css-ew64yg font-['Poppins:Regular',sans-serif] leading-[48px] left-[49.5px] not-italic text-[#111827] text-[48px] text-center top-[2px] translate-x-[-50%]">35.0</p>
      </div>
    </div>
  );
}

function Paragraph13() {
  return (
    <div className="h-[28px] relative shrink-0 w-[30px]" data-name="Paragraph">
      <div className="bg-clip-padding border-0 border-[transparent] border-solid relative size-full">
        <p className="absolute css-ew64yg font-['Poppins:Medium',sans-serif] leading-[20px] left-[15px] not-italic text-[#6b7280] text-[20px] text-center top-px translate-x-[-50%]">yrs</p>
      </div>
    </div>
  );
}

function Container3() {
  return (
    <div className="h-[48px] relative shrink-0 w-full" data-name="Container">
      <div className="flex flex-row items-end justify-center size-full">
        <div className="content-stretch flex gap-[8px] items-end justify-center pl-0 pr-[0.008px] py-0 relative size-full">
          <Paragraph12 />
          <Paragraph13 />
        </div>
      </div>
    </div>
  );
}

function MetricCardWithUnit1() {
  return (
    <div className="absolute content-stretch flex flex-col gap-[8px] h-[77px] items-start left-[618.66px] top-0 w-[586.664px]" data-name="MetricCardWithUnit">
      <Paragraph11 />
      <Container3 />
    </div>
  );
}

function Paragraph14() {
  return (
    <div className="h-[21px] relative shrink-0 w-full" data-name="Paragraph">
      <p className="absolute css-ew64yg font-['Poppins:SemiBold',sans-serif] leading-[21px] left-[293.68px] not-italic text-[#6b7280] text-[14px] text-center top-[0.5px] translate-x-[-50%]">AGE RANGE OF COVERED LIVES</p>
    </div>
  );
}

function Paragraph15() {
  return (
    <div className="h-[48px] relative shrink-0 w-[144.773px]" data-name="Paragraph">
      <div className="bg-clip-padding border-0 border-[transparent] border-solid relative size-full">
        <p className="absolute css-ew64yg font-['Poppins:Regular',sans-serif] leading-[48px] left-[72.5px] not-italic text-[#111827] text-[48px] text-center top-[2px] translate-x-[-50%]">7 – 58</p>
      </div>
    </div>
  );
}

function Paragraph16() {
  return (
    <div className="h-[28px] relative shrink-0 w-[30px]" data-name="Paragraph">
      <div className="bg-clip-padding border-0 border-[transparent] border-solid relative size-full">
        <p className="absolute css-ew64yg font-['Poppins:Medium',sans-serif] leading-[20px] left-[15px] not-italic text-[#6b7280] text-[20px] text-center top-px translate-x-[-50%]">yrs</p>
      </div>
    </div>
  );
}

function Container4() {
  return (
    <div className="h-[48px] relative shrink-0 w-full" data-name="Container">
      <div className="flex flex-row items-end justify-center size-full">
        <div className="content-stretch flex gap-[8px] items-end justify-center pl-0 pr-[0.008px] py-0 relative size-full">
          <Paragraph15 />
          <Paragraph16 />
        </div>
      </div>
    </div>
  );
}

function MetricCardWithUnit2() {
  return (
    <div className="absolute content-stretch flex flex-col gap-[8px] h-[77px] items-start left-[1237.33px] top-0 w-[586.672px]" data-name="MetricCardWithUnit">
      <Paragraph14 />
      <Container4 />
    </div>
  );
}

function Container5() {
  return (
    <div className="absolute border-[#06b6d4] border-b-3 border-solid h-[112px] left-[48px] top-[255px] w-[1824px]" data-name="Container">
      <MetricCardWithUnit />
      <MetricCardWithUnit1 />
      <MetricCardWithUnit2 />
    </div>
  );
}

function Heading1() {
  return (
    <div className="h-[30px] relative shrink-0 w-full" data-name="Heading 2">
      <p className="absolute css-ew64yg font-['Poppins:Bold',sans-serif] leading-[30px] left-0 not-italic text-[#111827] text-[20px] top-px">Employee Demographics</p>
    </div>
  );
}

function Text1() {
  return (
    <div className="h-[24px] relative shrink-0 w-[132.344px]" data-name="Text">
      <div className="bg-clip-padding border-0 border-[transparent] border-solid relative size-full">
        <p className="absolute css-ew64yg font-['Poppins:Regular',sans-serif] leading-[24px] left-0 not-italic text-[#4b5563] text-[16px] top-[0.5px]">Total employees</p>
      </div>
    </div>
  );
}

function Text2() {
  return (
    <div className="h-[24px] relative shrink-0 w-[20.68px]" data-name="Text">
      <div className="bg-clip-padding border-0 border-[transparent] border-solid relative size-full">
        <p className="absolute css-ew64yg font-['Poppins:Bold',sans-serif] leading-[24px] left-0 not-italic text-[#111827] text-[16px] top-[0.5px]">49</p>
      </div>
    </div>
  );
}

function InfoRow() {
  return (
    <div className="content-stretch flex gap-[12px] h-[24px] items-start relative shrink-0 w-full" data-name="InfoRow">
      <Text1 />
      <Text2 />
    </div>
  );
}

function Text3() {
  return (
    <div className="h-[24px] relative shrink-0 w-[103.031px]" data-name="Text">
      <div className="bg-clip-padding border-0 border-[transparent] border-solid relative size-full">
        <p className="absolute css-ew64yg font-['Poppins:Regular',sans-serif] leading-[24px] left-0 not-italic text-[#4b5563] text-[16px] top-[0.5px]">Average age</p>
      </div>
    </div>
  );
}

function Text4() {
  return (
    <div className="h-[24px] relative shrink-0 w-[80.625px]" data-name="Text">
      <div className="bg-clip-padding border-0 border-[transparent] border-solid relative size-full">
        <p className="absolute css-ew64yg font-['Poppins:Regular',sans-serif] leading-[24px] left-0 not-italic text-[#111827] text-[16px] top-[0.5px]">39.3 years</p>
      </div>
    </div>
  );
}

function InfoRow1() {
  return (
    <div className="content-stretch flex gap-[12px] h-[24px] items-start relative shrink-0 w-full" data-name="InfoRow">
      <Text3 />
      <Text4 />
    </div>
  );
}

function Text5() {
  return (
    <div className="h-[24px] relative shrink-0 w-[95.328px]" data-name="Text">
      <div className="bg-clip-padding border-0 border-[transparent] border-solid relative size-full">
        <p className="absolute css-ew64yg font-['Poppins:Regular',sans-serif] leading-[24px] left-0 not-italic text-[#4b5563] text-[16px] top-[0.5px]">Median age</p>
      </div>
    </div>
  );
}

function Text6() {
  return (
    <div className="h-[24px] relative shrink-0 w-[79.906px]" data-name="Text">
      <div className="bg-clip-padding border-0 border-[transparent] border-solid relative size-full">
        <p className="absolute css-ew64yg font-['Poppins:Regular',sans-serif] leading-[24px] left-0 not-italic text-[#111827] text-[16px] top-[0.5px]">37.0 years</p>
      </div>
    </div>
  );
}

function InfoRow2() {
  return (
    <div className="content-stretch flex gap-[12px] h-[24px] items-start relative shrink-0 w-full" data-name="InfoRow">
      <Text5 />
      <Text6 />
    </div>
  );
}

function Paragraph17() {
  return (
    <div className="h-[24px] relative shrink-0 w-full" data-name="Paragraph">
      <p className="absolute css-ew64yg font-['Poppins:Bold',sans-serif] leading-[24px] left-0 not-italic text-[#111827] text-[16px] top-[0.5px]">Age range</p>
    </div>
  );
}

function Text7() {
  return (
    <div className="h-[24px] relative shrink-0 w-[74.977px]" data-name="Text">
      <div className="bg-clip-padding border-0 border-[transparent] border-solid relative size-full">
        <p className="absolute css-ew64yg font-['Poppins:Regular',sans-serif] leading-[24px] left-0 not-italic text-[#4b5563] text-[16px] top-[0.5px]">Youngest</p>
      </div>
    </div>
  );
}

function Text8() {
  return (
    <div className="h-[24px] relative shrink-0 w-[67.602px]" data-name="Text">
      <div className="bg-clip-padding border-0 border-[transparent] border-solid relative size-full">
        <p className="absolute css-ew64yg font-['Poppins:Regular',sans-serif] leading-[24px] left-0 not-italic text-[#111827] text-[16px] top-[0.5px]">24 years</p>
      </div>
    </div>
  );
}

function InfoRow3() {
  return (
    <div className="content-stretch flex gap-[12px] h-[24px] items-start relative shrink-0 w-full" data-name="InfoRow">
      <Text7 />
      <Text8 />
    </div>
  );
}

function Text9() {
  return (
    <div className="h-[24px] relative shrink-0 w-[51.43px]" data-name="Text">
      <div className="bg-clip-padding border-0 border-[transparent] border-solid relative size-full">
        <p className="absolute css-ew64yg font-['Poppins:Regular',sans-serif] leading-[24px] left-0 not-italic text-[#4b5563] text-[16px] top-[0.5px]">Oldest</p>
      </div>
    </div>
  );
}

function Text10() {
  return (
    <div className="h-[24px] relative shrink-0 w-[68.484px]" data-name="Text">
      <div className="bg-clip-padding border-0 border-[transparent] border-solid relative size-full">
        <p className="absolute css-ew64yg font-['Poppins:Regular',sans-serif] leading-[24px] left-0 not-italic text-[#111827] text-[16px] top-[0.5px]">58 years</p>
      </div>
    </div>
  );
}

function InfoRow4() {
  return (
    <div className="content-stretch flex gap-[12px] h-[24px] items-start relative shrink-0 w-full" data-name="InfoRow">
      <Text9 />
      <Text10 />
    </div>
  );
}

function Container6() {
  return (
    <div className="h-[52px] relative shrink-0 w-full" data-name="Container">
      <div className="content-stretch flex flex-col gap-[4px] items-start pl-[8px] pr-0 py-0 relative size-full">
        <InfoRow3 />
        <InfoRow4 />
      </div>
    </div>
  );
}

function Container7() {
  return (
    <div className="content-stretch flex flex-col gap-[8px] h-[100px] items-start pb-0 pt-[16px] px-0 relative shrink-0 w-full" data-name="Container">
      <Paragraph17 />
      <Container6 />
    </div>
  );
}

function Container8() {
  return (
    <div className="content-stretch flex flex-col gap-[12px] h-[208px] items-start relative shrink-0 w-full" data-name="Container">
      <InfoRow />
      <InfoRow1 />
      <InfoRow2 />
      <Container7 />
    </div>
  );
}

function Container9() {
  return (
    <div className="col-[1] content-stretch css-vsca90 flex flex-col gap-[24px] items-start relative row-[1] self-stretch shrink-0" data-name="Container">
      <Heading1 />
      <Container8 />
    </div>
  );
}

function Heading3() {
  return (
    <div className="h-[30px] relative shrink-0 w-full" data-name="Heading 2">
      <p className="absolute css-ew64yg font-['Poppins:Bold',sans-serif] leading-[30px] left-0 not-italic text-[#111827] text-[20px] top-px">Dependent Overview</p>
    </div>
  );
}

function Paragraph18() {
  return (
    <div className="h-[18px] relative shrink-0 w-full" data-name="Paragraph">
      <p className="absolute css-ew64yg font-['Poppins:Bold',sans-serif] leading-[18px] left-0 not-italic text-[#6b7280] text-[12px] top-[0.5px]">TOTAL DEPENDENTS</p>
    </div>
  );
}

function Paragraph19() {
  return (
    <div className="h-[28px] relative shrink-0 w-full" data-name="Paragraph">
      <p className="absolute css-ew64yg font-['Poppins:Bold',sans-serif] leading-[28px] left-0 not-italic text-[#111827] text-[28px] top-px">14</p>
    </div>
  );
}

function ColorCard() {
  return (
    <div className="bg-[rgba(250,245,255,0.5)] col-[1] css-por8k5 relative rounded-[14px] row-[1] self-stretch shrink-0" data-name="ColorCard">
      <div aria-hidden="true" className="absolute border-[#a855f7] border-l-4 border-solid inset-0 pointer-events-none rounded-[14px]" />
      <div className="content-stretch flex flex-col gap-[4px] items-start pb-0 pl-[20px] pr-[16px] pt-[16px] relative size-full">
        <Paragraph18 />
        <Paragraph19 />
      </div>
    </div>
  );
}

function Paragraph20() {
  return (
    <div className="h-[18px] relative shrink-0 w-full" data-name="Paragraph">
      <p className="absolute css-ew64yg font-['Poppins:Bold',sans-serif] leading-[18px] left-0 not-italic text-[#6b7280] text-[12px] top-[0.5px]">COVERAGE BURDEN</p>
    </div>
  );
}

function Paragraph21() {
  return (
    <div className="h-[28px] relative shrink-0 w-full" data-name="Paragraph">
      <p className="absolute css-ew64yg font-['Poppins:Bold',sans-serif] leading-[28px] left-0 not-italic text-[#111827] text-[28px] top-px">1.29:1</p>
    </div>
  );
}

function ColorCard1() {
  return (
    <div className="bg-[rgba(236,254,255,0.5)] col-[2] css-por8k5 relative rounded-[14px] row-[1] self-stretch shrink-0" data-name="ColorCard">
      <div aria-hidden="true" className="absolute border-[#06b6d4] border-l-4 border-solid inset-0 pointer-events-none rounded-[14px]" />
      <div className="content-stretch flex flex-col gap-[4px] items-start pb-0 pl-[20px] pr-[16px] pt-[16px] relative size-full">
        <Paragraph20 />
        <Paragraph21 />
      </div>
    </div>
  );
}

function Paragraph22() {
  return (
    <div className="h-[18px] relative shrink-0 w-full" data-name="Paragraph">
      <p className="absolute css-ew64yg font-['Poppins:Bold',sans-serif] leading-[18px] left-0 not-italic text-[#6b7280] text-[12px] top-[0.5px]">AVERAGE AGE</p>
    </div>
  );
}

function Paragraph23() {
  return (
    <div className="h-[28px] relative shrink-0 w-full" data-name="Paragraph">
      <p className="absolute css-ew64yg font-['Poppins:Bold',sans-serif] leading-[28px] left-0 not-italic text-[#111827] text-[28px] top-px">18.4</p>
    </div>
  );
}

function ColorCard2() {
  return (
    <div className="bg-[rgba(240,253,244,0.5)] col-[3] css-por8k5 relative rounded-[14px] row-[1] self-stretch shrink-0" data-name="ColorCard">
      <div aria-hidden="true" className="absolute border-[#22c55e] border-l-4 border-solid inset-0 pointer-events-none rounded-[14px]" />
      <div className="content-stretch flex flex-col gap-[4px] items-start pb-0 pl-[20px] pr-[16px] pt-[16px] relative size-full">
        <Paragraph22 />
        <Paragraph23 />
      </div>
    </div>
  );
}

function Paragraph24() {
  return (
    <div className="h-[18px] relative shrink-0 w-full" data-name="Paragraph">
      <p className="absolute css-ew64yg font-['Poppins:Bold',sans-serif] leading-[18px] left-0 not-italic text-[#6b7280] text-[12px] top-[0.5px]">AGE RANGE</p>
    </div>
  );
}

function Paragraph25() {
  return (
    <div className="h-[28px] relative shrink-0 w-full" data-name="Paragraph">
      <p className="absolute css-ew64yg font-['Poppins:Bold',sans-serif] leading-[28px] left-0 not-italic text-[#111827] text-[28px] top-px">7-51</p>
    </div>
  );
}

function ColorCard3() {
  return (
    <div className="bg-[rgba(255,247,237,0.5)] col-[4] css-por8k5 relative rounded-[14px] row-[1] self-stretch shrink-0" data-name="ColorCard">
      <div aria-hidden="true" className="absolute border-[#f97316] border-l-4 border-solid inset-0 pointer-events-none rounded-[14px]" />
      <div className="content-stretch flex flex-col gap-[4px] items-start pb-0 pl-[20px] pr-[16px] pt-[16px] relative size-full">
        <Paragraph24 />
        <Paragraph25 />
      </div>
    </div>
  );
}

function Container10() {
  return (
    <div className="gap-[16px] grid grid-cols-[repeat(4,_minmax(0,_1fr))] grid-rows-[repeat(1,_minmax(0,_1fr))] h-[82px] relative shrink-0 w-full" data-name="Container">
      <ColorCard />
      <ColorCard1 />
      <ColorCard2 />
      <ColorCard3 />
    </div>
  );
}

function Heading2() {
  return (
    <div className="h-[24px] relative shrink-0 w-full" data-name="Heading 3">
      <p className="absolute css-ew64yg font-['Poppins:Bold',sans-serif] leading-[24px] left-0 not-italic text-[#111827] text-[16px] top-[0.5px]">By relationship</p>
    </div>
  );
}

function Text11() {
  return (
    <div className="h-[21px] relative shrink-0 w-[58.984px]" data-name="Text">
      <div className="bg-clip-padding border-0 border-[transparent] border-solid relative size-full">
        <p className="absolute css-ew64yg font-['Poppins:Regular',sans-serif] leading-[21px] left-0 not-italic text-[#374151] text-[14px] top-[0.5px]">Children</p>
      </div>
    </div>
  );
}

function Text12() {
  return (
    <div className="h-[21px] relative shrink-0 w-[56.875px]" data-name="Text">
      <div className="bg-clip-padding border-0 border-[transparent] border-solid relative size-full">
        <p className="absolute css-ew64yg font-['Poppins:Regular',sans-serif] leading-[21px] left-0 not-italic text-[#4b5563] text-[14px] top-[0.5px]">13 (93%)</p>
      </div>
    </div>
  );
}

function Container11() {
  return (
    <div className="content-stretch flex h-[21px] items-start justify-between relative shrink-0 w-full" data-name="Container">
      <Text11 />
      <Text12 />
    </div>
  );
}

function Container12() {
  return <div className="bg-[#3b82f6] h-[12px] rounded-[16777200px] shrink-0 w-full" data-name="Container" />;
}

function Container13() {
  return (
    <div className="bg-[#e5e7eb] h-[12px] relative rounded-[16777200px] shrink-0 w-full" data-name="Container">
      <div className="content-stretch flex flex-col items-start pl-0 pr-[44.523px] py-0 relative size-full">
        <Container12 />
      </div>
    </div>
  );
}

function Container14() {
  return (
    <div className="content-stretch flex flex-col gap-[8px] h-[41px] items-start relative shrink-0 w-full" data-name="Container">
      <Container11 />
      <Container13 />
    </div>
  );
}

function Text13() {
  return (
    <div className="h-[21px] relative shrink-0 w-[58.898px]" data-name="Text">
      <div className="bg-clip-padding border-0 border-[transparent] border-solid relative size-full">
        <p className="absolute css-ew64yg font-['Poppins:Regular',sans-serif] leading-[21px] left-0 not-italic text-[#374151] text-[14px] top-[0.5px]">Spouses</p>
      </div>
    </div>
  );
}

function Text14() {
  return (
    <div className="h-[21px] relative shrink-0 w-[39.203px]" data-name="Text">
      <div className="bg-clip-padding border-0 border-[transparent] border-solid relative size-full">
        <p className="absolute css-ew64yg font-['Poppins:Regular',sans-serif] leading-[21px] left-0 not-italic text-[#4b5563] text-[14px] top-[0.5px]">1 (7%)</p>
      </div>
    </div>
  );
}

function Container15() {
  return (
    <div className="content-stretch flex h-[21px] items-start justify-between relative shrink-0 w-full" data-name="Container">
      <Text13 />
      <Text14 />
    </div>
  );
}

function Container16() {
  return <div className="bg-[#f472b6] h-[12px] rounded-[16777200px] shrink-0 w-full" data-name="Container" />;
}

function Container17() {
  return (
    <div className="bg-[#e5e7eb] h-[12px] relative rounded-[16777200px] shrink-0 w-full" data-name="Container">
      <div className="content-stretch flex flex-col items-start pl-0 pr-[591.484px] py-0 relative size-full">
        <Container16 />
      </div>
    </div>
  );
}

function Container18() {
  return (
    <div className="content-stretch flex flex-col gap-[8px] h-[41px] items-start relative shrink-0 w-full" data-name="Container">
      <Container15 />
      <Container17 />
    </div>
  );
}

function Container19() {
  return (
    <div className="content-stretch flex flex-col gap-[16px] h-[98px] items-start relative shrink-0 w-full" data-name="Container">
      <Container14 />
      <Container18 />
    </div>
  );
}

function Container20() {
  return (
    <div className="bg-[#f9fafb] col-[1] css-por8k5 relative rounded-[14px] row-[1] self-stretch shrink-0" data-name="Container">
      <div className="content-stretch flex flex-col gap-[16px] items-start pb-0 pt-[24px] px-[24px] relative size-full">
        <Heading2 />
        <Container19 />
      </div>
    </div>
  );
}

function Heading4() {
  return (
    <div className="h-[24px] relative shrink-0 w-full" data-name="Heading 3">
      <p className="absolute css-ew64yg font-['Poppins:Bold',sans-serif] leading-[24px] left-0 not-italic text-[#111827] text-[16px] top-[0.5px]">Dependents age statistics</p>
    </div>
  );
}

function Text15() {
  return (
    <div className="h-[24px] relative shrink-0 w-[67.203px]" data-name="Text">
      <div className="bg-clip-padding border-0 border-[transparent] border-solid relative size-full">
        <p className="absolute css-ew64yg font-['Poppins:Regular',sans-serif] leading-[24px] left-0 not-italic text-[#4b5563] text-[16px] top-[0.5px]">Average</p>
      </div>
    </div>
  );
}

function Text16() {
  return (
    <div className="h-[24px] relative shrink-0 w-[81.734px]" data-name="Text">
      <div className="bg-clip-padding border-0 border-[transparent] border-solid relative size-full">
        <p className="absolute css-ew64yg font-['Poppins:Bold',sans-serif] leading-[24px] left-0 not-italic text-[#111827] text-[16px] top-[0.5px]">18.4 years</p>
      </div>
    </div>
  );
}

function Container21() {
  return (
    <div className="content-stretch flex h-[24px] items-start justify-between relative shrink-0 w-full" data-name="Container">
      <Text15 />
      <Text16 />
    </div>
  );
}

function Text17() {
  return (
    <div className="h-[24px] relative shrink-0 w-[59.508px]" data-name="Text">
      <div className="bg-clip-padding border-0 border-[transparent] border-solid relative size-full">
        <p className="absolute css-ew64yg font-['Poppins:Regular',sans-serif] leading-[24px] left-0 not-italic text-[#4b5563] text-[16px] top-[0.5px]">Median</p>
      </div>
    </div>
  );
}

function Text18() {
  return (
    <div className="h-[24px] relative shrink-0 w-[79.523px]" data-name="Text">
      <div className="bg-clip-padding border-0 border-[transparent] border-solid relative size-full">
        <p className="absolute css-ew64yg font-['Poppins:Bold',sans-serif] leading-[24px] left-0 not-italic text-[#111827] text-[16px] top-[0.5px]">17.0 years</p>
      </div>
    </div>
  );
}

function Container22() {
  return (
    <div className="content-stretch flex h-[24px] items-start justify-between relative shrink-0 w-full" data-name="Container">
      <Text17 />
      <Text18 />
    </div>
  );
}

function Container23() {
  return (
    <div className="content-stretch flex flex-col gap-[12px] h-[60px] items-start relative shrink-0 w-full" data-name="Container">
      <Container21 />
      <Container22 />
    </div>
  );
}

function Container24() {
  return (
    <div className="bg-[#f9fafb] col-[2] css-por8k5 relative rounded-[14px] row-[1] self-stretch shrink-0" data-name="Container">
      <div className="content-stretch flex flex-col gap-[16px] items-start pb-0 pt-[24px] px-[24px] relative size-full">
        <Heading4 />
        <Container23 />
      </div>
    </div>
  );
}

function Container25() {
  return (
    <div className="gap-[24px] grid grid-cols-[repeat(2,_minmax(0,_1fr))] grid-rows-[repeat(1,_minmax(0,_1fr))] h-[186px] relative shrink-0 w-full" data-name="Container">
      <Container20 />
      <Container24 />
    </div>
  );
}

function Container26() {
  return (
    <div className="col-[2] content-stretch css-vsca90 flex flex-col gap-[16px] h-[338px] items-start relative row-[1] shrink-0" data-name="Container">
      <Heading3 />
      <Container10 />
      <Container25 />
    </div>
  );
}

function Container27() {
  return (
    <div className="absolute gap-[32px] grid grid-cols-[__minmax(0,_400fr)_minmax(0,_1fr)] grid-rows-[repeat(1,_minmax(0,_1fr))] h-[569px] left-[48px] top-[399px] w-[1824px]" data-name="Container">
      <Container9 />
      <Container26 />
    </div>
  );
}

function Paragraph26() {
  return (
    <div className="h-[18px] relative shrink-0 w-full" data-name="Paragraph">
      <p className="absolute css-ew64yg font-['Poppins:Regular',sans-serif] leading-[18px] left-0 not-italic text-[#9ca3af] text-[12px] top-[0.5px]">Coverage burden = (employees + dependents) / employees = (49 + 14) / 49 = 1.29 covered lives per employee</p>
    </div>
  );
}

function Paragraph27() {
  return (
    <div className="h-[18px] relative shrink-0 w-full" data-name="Paragraph">
      <p className="absolute css-ew64yg font-['Poppins:Regular',sans-serif] leading-[18px] left-0 not-italic text-[#9ca3af] text-[12px] top-[0.5px]">Generated by Glove Benefits | 01.16.26</p>
    </div>
  );
}

function Container28() {
  return (
    <div className="absolute content-stretch flex flex-col gap-[4px] h-[40px] items-start left-[48px] top-[992px] w-[1824px]" data-name="Container">
      <Paragraph26 />
      <Paragraph27 />
    </div>
  );
}

export default function OptimizeScreenLayout() {
  return (
    <div className="bg-white relative size-full" data-name="Optimize Screen Layout">
      <Container />
      <Container1 />
      <Container5 />
      <Container27 />
      <Container28 />
    </div>
  );
}